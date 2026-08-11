#!/usr/bin/env python
"""cadctl.py -- the CAD OS Layer control surface (Lane B1).

`Cad` is a thin, truthful orchestrator over the existing AutoCAD SDK router. It
never parses a DWG itself: it stages a COPY of an input drawing under
staging/golden/<ts>/ and drives tools/autocad-router.ps1 (ObjectARX ->
ObjectDBX -> AutoLISP) to produce a dwg_geometry_extract.v1 JSON, then normalizes
that to the engine-neutral ariadne.dwg_graph_ir.v1 via tools/ir_builder.py.

Invariants honored here:
  * Original DWG files are READ-ONLY. inspect() always operates on a staged copy.
  * No-fake-success. If the router extraction is unavailable/fails, or a required
    sibling module (ir_builder / sqlite_ir_store / validator) is absent, the
    method returns a truthful status (not_implemented / unavailable / partial /
    blocked) -- never a faked ok.
  * status() READS the published router status JSON read-only; it never runs
    `-Action status`.
  * Every external command's stdout + stderr + exit code is captured into out_dir.

Standard library only (json, sqlite3 are stdlib). Config/status JSON on this box
is BOM-prefixed -> read with encoding="utf-8-sig".
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parent
CONFIG_DIR = ROUTER_HOME / "config"
REPORTS_DIR = ROUTER_HOME / "reports"
STAGING_GOLDEN_DIR = ROUTER_HOME / "staging" / "golden"

STATUS_JSON = REPORTS_DIR / "autocad_router_status_latest.json"
OPERATIONS_V2 = CONFIG_DIR / "operations.v2.json"
DISPLAY_MEMBERSHIP_STRICT_LAYER_ENTITIES_V1 = "strict_layer_entities_v1"
DISPLAY_MEMBERSHIP_LINEAR_SEGMENTS_V1 = "linear_segments_v1"
DISPLAY_MEMBERSHIP_GEOMETRY_SCOPES = frozenset({
    DISPLAY_MEMBERSHIP_STRICT_LAYER_ENTITIES_V1,
    DISPLAY_MEMBERSHIP_LINEAR_SEGMENTS_V1,
})
NATIVE_BUILD_MANIFEST_NAME = "native_build_manifest.json"
NATIVE_BUILD_MANIFEST_SCHEMA = "ariadne.cad_os.native_build_manifest.v1"
NATIVE_BUILD_MANIFEST_VERSION = 1
DISPLAY_MEMBERSHIP_REQUIRED_ARTIFACTS = (
    "Ariadne.AcadNativeDbx.dbx",
    "Ariadne.AcadNative.crx",
    "Ariadne.AcadNative.arx",
)
_NATIVE_SOURCE_ROOTS = (
    Path("src") / "Ariadne.AcadNative",
    Path("src") / "Ariadne.AcadNativeDbx",
)
_NATIVE_BUILD_OUTPUT_DIRS = frozenset({"bin", "obj", ".vs", "build"})
_NATIVE_BUILD_RECIPE_PATH = Path("tools") / "build_native_acad.ps1"
_NATIVE_SOURCE_GIT_PATHS = (
    "src/Ariadne.AcadNative",
    "src/Ariadne.AcadNativeDbx",
)

# Ensure sibling tools/*.py are importable when cadctl is imported by path.
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import run_job  # noqa: E402  (sibling helper, Lane B1)
import normalize_result  # noqa: E402  (sibling helper, Lane B1)
import route_select  # noqa: E402  (sibling helper, Lane B1)
import attended_lane  # noqa: E402  (dedicated full-AutoCAD one-shot lane)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


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
    """Parse evidence JSON without Python's duplicate/non-finite extensions."""
    return json.loads(
        value,
        object_pairs_hook=_reject_duplicate_json_object,
        parse_constant=_reject_json_constant,
    )


def _load_json_bom(path: Path) -> dict:
    return _strict_json_loads(Path(path).read_text(encoding="utf-8-sig"))


def _is_plain_int(value: object) -> bool:
    """JSON booleans are not valid integer evidence, despite Python's type tree."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_nonnegative_plain_int(value: object) -> bool:
    return _is_plain_int(value) and value >= 0


def _is_positive_plain_int(value: object) -> bool:
    return _is_plain_int(value) and value > 0


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_finite_point2(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(
            isinstance(coordinate, (int, float))
            and not isinstance(coordinate, bool)
            and math.isfinite(float(coordinate))
            for coordinate in value
        )
    )


def _sha256_head(path: Path, n: int = 16) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n].upper()


def _sha256_file(path: Path) -> str:
    """Return the full lowercase SHA-256 of a local evidence file."""
    return _sha256_head(path, 64).lower()


def _read_only_file_state(path: Path) -> dict:
    """Return the OS-enforced read-only state used by observation-only DWGs."""
    state = {
        "path": str(Path(os.path.abspath(str(path)))),
        "read_only": False,
        "mode": None,
        "writable_mode_bits": None,
        "windows_file_attributes": None,
        "windows_read_only_attribute": None,
        "reason": None,
    }
    try:
        file_stat = path.stat()
        mode = stat.S_IMODE(file_stat.st_mode)
        writable_mode_bits = bool(
            mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        )
        state["mode"] = f"0o{mode:o}"
        state["writable_mode_bits"] = writable_mode_bits
        if os.name == "nt":
            attributes = getattr(file_stat, "st_file_attributes", None)
            has_read_only_attribute = (
                isinstance(attributes, int)
                and bool(attributes & stat.FILE_ATTRIBUTE_READONLY)
            )
            state["windows_file_attributes"] = attributes
            state["windows_read_only_attribute"] = has_read_only_attribute
            state["read_only"] = has_read_only_attribute and not writable_mode_bits
        else:
            state["read_only"] = not writable_mode_bits
        state["reason"] = (
            "OS read-only attribute and mode are enforced"
            if state["read_only"]
            else "file remains writable at the OS boundary"
        )
    except OSError as exc:
        state["reason"] = f"{type(exc).__name__}: {exc}"
    return state


def _canonical_json_bytes(value: object) -> bytes:
    """Stable JSON encoding used only to compare independently supplied facts."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


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
    """Treat symbolic links and Windows reparse points as containment escapes."""
    metadata = os.lstat(path)
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _canonical_native_source_bytes(raw: bytes) -> bytes:
    """Ignore checkout-only CRLF expansion while preserving binary inputs."""
    if b"\0" in raw:
        return raw
    return raw.replace(b"\r\n", b"\n")


def _native_source_inputs(router_home: Path) -> list[dict]:
    """Enumerate the native source tree without build output or reparse inputs."""
    inputs: list[dict] = []
    for relative_root in _NATIVE_SOURCE_ROOTS:
        root = router_home / relative_root
        if not root.is_dir() or _path_reparse_error(root) is not None:
            raise FileNotFoundError(f"native source root is missing: {root}")
        for current_text, directory_names, file_names in os.walk(
            root, topdown=True, followlinks=False
        ):
            current = Path(current_text)
            if _is_reparse_point(current):
                raise OSError(f"native source directory is a reparse point: {current}")
            retained_directories = []
            for name in directory_names:
                child = current / name
                if _is_reparse_point(child):
                    raise OSError(f"native source directory is a reparse point: {child}")
                if not _is_native_build_output_component(name):
                    retained_directories.append(name)
            directory_names[:] = retained_directories
            for name in file_names:
                path = current / name
                if _is_reparse_point(path):
                    raise OSError(f"native source input is a reparse point: {path}")
                raw = _canonical_native_source_bytes(path.read_bytes())
                inputs.append(
                    {
                        "path": path.relative_to(router_home).as_posix(),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "bytes": len(raw),
                    }
                )
    inputs.sort(key=lambda entry: entry["path"].casefold())
    if not inputs:
        raise FileNotFoundError("native source input inventory is empty")
    return inputs


def _native_status_line_tracks_source(line: str) -> bool:
    """Keep source changes but discard generated build-output status rows."""
    payload = line[3:] if len(line) >= 3 else line
    for candidate in payload.split(" -> "):
        normalized = candidate.strip().strip('"').replace("\\", "/")
        if not any(
            _is_native_build_output_component(part)
            for part in Path(normalized).parts
        ):
            return True
    return False


def _native_source_git_state(router_home: Path) -> dict:
    """Read Git state only for native source inputs, never the whole worktree."""
    unknown = {
        "available": False,
        "head": "UNKNOWN",
        "native_source_dirty": "UNKNOWN",
        "native_source_status_sha256": "UNKNOWN",
    }
    try:
        safe_directory = f"safe.directory={router_home.resolve()}"
        head_result = subprocess.run(
            [
                "git",
                "-c",
                safe_directory,
                "-C",
                str(router_home),
                "rev-parse",
                "HEAD",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        if head_result.returncode != 0:
            return unknown
        head = head_result.stdout.decode("utf-8", errors="strict").strip()
        if not head:
            return unknown
        status_result = subprocess.run(
            [
                "git",
                "-c",
                safe_directory,
                "-C",
                str(router_home),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                *_NATIVE_SOURCE_GIT_PATHS,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        if status_result.returncode != 0:
            return unknown
        status_lines = status_result.stdout.decode(
            "utf-8", errors="strict"
        ).splitlines()
        status_text = "\n".join(
            line for line in status_lines if _native_status_line_tracks_source(line)
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        return unknown
    return {
        "available": True,
        "head": head,
        "native_source_dirty": bool(status_text),
        "native_source_status_sha256": hashlib.sha256(
            status_text.encode("utf-8")
        ).hexdigest(),
    }


def _build_recipe_state(router_home: Path) -> dict:
    """Return the exact checked-out build recipe identity, or explicit unknown."""
    recipe = router_home / _NATIVE_BUILD_RECIPE_PATH
    try:
        if not recipe.is_file() or _is_reparse_point(recipe):
            raise FileNotFoundError(recipe)
        sha256 = hashlib.sha256(
            _canonical_native_source_bytes(recipe.read_bytes())
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
        right_path = right.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False
    return os.path.normcase(str(left_path)) == os.path.normcase(str(right_path))


def _path_reparse_error(path: Path) -> str | None:
    """Return an error for an existing reparse component on an absolute path."""
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


@contextmanager
def _hold_windows_paths_stable(paths: list[Path]):
    """Deny write/delete replacement while the final receipt is committed.

    A hash check followed by an atomic receipt link still has a race unless the
    checked files and containing directories remain locked through that link.
    Display membership is a Windows/AutoCAD-only route, so unsupported hosts
    fail closed rather than silently weakening this publication boundary.
    """
    if os.name != "nt":
        raise OSError("stable evidence publication requires Windows file locking")

    import ctypes
    from ctypes import wintypes

    create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
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
    close_handle = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    generic_read = 0x80000000
    file_share_read = 0x00000001
    open_existing = 3
    file_attribute_normal = 0x00000080
    file_flag_backup_semantics = 0x02000000
    invalid_handle = wintypes.HANDLE(-1).value
    handles = []
    unique_paths: list[Path] = []
    seen: set[str] = set()
    try:
        for raw_path in paths:
            path = Path(os.path.abspath(str(raw_path)))
            key = os.path.normcase(str(path))
            if key in seen:
                continue
            seen.add(key)
            if _path_reparse_error(path) is not None or not path.exists():
                raise OSError(f"cannot lock missing or reparse evidence path: {path}")
            unique_paths.append(path)

        # Lock directories before their children so neither path identity nor
        # a checked leaf can be swapped before the receipt hard-link commits.
        unique_paths.sort(key=lambda value: (not value.is_dir(), len(value.parts), str(value)))
        for path in unique_paths:
            is_directory = path.is_dir()
            handle = create_file(
                str(path),
                0 if is_directory else generic_read,
                file_share_read,
                None,
                open_existing,
                file_flag_backup_semantics if is_directory else file_attribute_normal,
                None,
            )
            if handle == invalid_handle:
                code = ctypes.get_last_error()
                raise OSError(code, f"cannot hold stable evidence handle: {path}")
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            close_handle(handle)


def _display_output_roots(router_home: Path) -> tuple[Path, ...]:
    temp_root = Path(os.environ.get("TEMP") or tempfile.gettempdir())
    return (
        router_home / "staging",
        router_home / "runs",
        Path(r"D:\runs"),
        temp_root,
    )


def _validate_display_output_dir(out_dir: Path, router_home: Path) -> dict:
    """Resolve output containment, rejecting lexical and reparse-point escapes."""
    candidate = Path(os.path.abspath(str(out_dir)))
    candidate_error = _path_reparse_error(candidate)
    if candidate_error:
        return {"valid": False, "reason": candidate_error, "path": str(candidate)}
    if os.path.lexists(candidate) and not candidate.is_dir():
        return {
            "valid": False,
            "reason": f"output path exists but is not a directory: {candidate}",
            "path": str(candidate),
        }
    try:
        resolved_candidate = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        return {
            "valid": False,
            "reason": f"cannot resolve output path: {type(exc).__name__}: {exc}",
            "path": str(candidate),
        }
    root_errors = []
    for root in _display_output_roots(router_home):
        root_error = _path_reparse_error(root)
        if root_error:
            root_errors.append(root_error)
            continue
        try:
            resolved_root = root.resolve(strict=False)
            resolved_candidate.relative_to(resolved_root)
        except (OSError, RuntimeError, ValueError):
            continue
        if os.path.normcase(str(resolved_candidate)) == os.path.normcase(str(resolved_root)):
            continue
        return {
            "valid": True,
            "path": str(candidate),
            "resolved_path": str(resolved_candidate),
            "allowed_root": str(resolved_root),
        }
    reason = "output directory is outside permitted staging/, runs/, D:\\runs, or %TEMP% roots"
    if root_errors:
        reason += "; permitted-root inspection failed: " + "; ".join(root_errors)
    return {"valid": False, "reason": reason, "path": str(candidate)}


def _ensure_display_output_subdir(out_dir: Path, leaf: str, router_home: Path) -> Path:
    child = out_dir / leaf
    if os.path.lexists(child):
        raise FileExistsError(
            f"fresh display-membership output subdirectory already exists: {child}"
        )
    child.mkdir(parents=False, exist_ok=False)
    validation = _validate_display_output_dir(out_dir, router_home)
    if not validation.get("valid"):
        raise OSError(str(validation.get("reason") or "output containment changed"))
    try:
        child.resolve(strict=False).relative_to(out_dir.resolve(strict=False))
    except (OSError, RuntimeError, ValueError) as exc:
        raise OSError(f"output subdirectory escapes its containment root: {child}") from exc
    return child


def _validate_display_prelaunch_layout(
    out_dir: Path,
    staged_dir: Path,
    attended_dir: Path,
    router_home: Path,
) -> dict:
    """Require that only this invocation's new staging layout exists at launch."""
    containment = _validate_display_output_dir(out_dir, router_home)
    if not containment.get("valid"):
        return {
            "valid": False,
            "reason": "output containment changed: "
            + str(containment.get("reason")),
        }
    try:
        root_children = {child.name: child for child in out_dir.iterdir()}
        if set(root_children) != {"staged", "attended"}:
            return {
                "valid": False,
                "reason": "output directory gained unknown children before launch: "
                + ", ".join(sorted(root_children)),
            }
        for name, expected in (("staged", staged_dir), ("attended", attended_dir)):
            actual = root_children[name]
            if (
                not actual.is_dir()
                or _is_reparse_point(actual)
                or not _same_resolved_path(str(actual), expected)
            ):
                return {
                    "valid": False,
                    "reason": f"output {name} directory is not the safe directory created for this job",
                }
        staged_children = {child.name: child for child in staged_dir.iterdir()}
        if set(staged_children) != {"input.dwg"}:
            return {
                "valid": False,
                "reason": "staged output directory gained unknown children before launch: "
                + ", ".join(sorted(staged_children)),
            }
        staged_dwg = staged_children["input.dwg"]
        if not staged_dwg.is_file() or _is_reparse_point(staged_dwg):
            return {
                "valid": False,
                "reason": "staged DWG is missing or unsafe before launch",
            }
        attended_children = list(attended_dir.iterdir())
        if attended_children:
            return {
                "valid": False,
                "reason": "attended output directory is not fresh before launch: "
                + ", ".join(sorted(child.name for child in attended_children)),
            }
    except OSError as exc:
        return {
            "valid": False,
            "reason": f"cannot inspect fresh output layout: {type(exc).__name__}: {exc}",
        }
    return {"valid": True}


def _validate_display_runtime_layout(
    out_dir: Path,
    staged_dir: Path,
    attended_dir: Path,
    staged_dwg: Path,
    router_home: Path,
) -> dict:
    """Revalidate the path identities after an external AutoCAD process ran."""
    containment = _validate_display_output_dir(out_dir, router_home)
    if not containment.get("valid"):
        return {
            "valid": False,
            "reason": "output containment changed: " + str(containment.get("reason")),
        }
    try:
        for label, actual, expected in (
            ("staged", out_dir / "staged", staged_dir),
            ("attended", out_dir / "attended", attended_dir),
        ):
            if (
                not actual.is_dir()
                or _is_reparse_point(actual)
                or not _same_resolved_path(str(actual), expected)
            ):
                return {
                    "valid": False,
                    "reason": f"output {label} directory identity changed during execution",
                }
        actual_staged = staged_dir / "input.dwg"
        if (
            not actual_staged.is_file()
            or _is_reparse_point(actual_staged)
            or not _same_resolved_path(str(actual_staged), staged_dwg)
        ):
            return {
                "valid": False,
                "reason": "staged DWG identity changed during execution",
            }
    except OSError as exc:
        return {
            "valid": False,
            "reason": f"cannot revalidate runtime layout: {type(exc).__name__}: {exc}",
        }
    return {"valid": True}


def _atomic_write_json_no_overwrite(
    path: Path,
    payload: dict,
    *,
    before_publish=None,
) -> None:
    """Publish complete JSON evidence once; a competing destination is an error."""
    if os.path.lexists(path):
        raise FileExistsError(f"refusing to overwrite existing evidence: {path}")
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    published = False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # os.replace would silently destroy an existing receipt. A same-volume
        # hard-link creates the final name atomically and fails on a race. Hold
        # the temporary inode stable as well as the caller's evidence set: the
        # final name is only trustworthy if the exact encoded payload remained
        # immutable until the link was created.
        guard_context = before_publish() if before_publish is not None else nullcontext()
        with _hold_windows_paths_stable([temporary]):
            if temporary.read_bytes() != encoded:
                raise OSError("temporary evidence bytes changed before publication")
            with guard_context:
                if temporary.read_bytes() != encoded:
                    raise OSError("temporary evidence bytes changed inside publication guard")
                os.link(temporary, path)
                published = True
                if (
                    not os.path.samefile(temporary, path)
                    or path.stat().st_size != len(encoded)
                    or path.read_bytes() != encoded
                ):
                    raise OSError("published evidence bytes do not match the final payload")
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            # Once the no-overwrite hard-link has succeeded, the destination is
            # authoritative. A best-effort cleanup failure must not turn a
            # persisted PASS receipt into a contradictory BLOCKED return.
            if not published:
                raise


def _pe64_image_state(path: Path) -> dict:
    """Validate the minimum structural facts of an x64 PE32+ DLL image."""
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
        raw = path.read_bytes()
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
        optional_bytes = int.from_bytes(
            raw[pe_offset + 20 : pe_offset + 22], "little"
        )
        characteristics = int.from_bytes(
            raw[pe_offset + 22 : pe_offset + 24], "little"
        )
        optional_offset = pe_offset + 24
        if optional_offset + optional_bytes > len(raw):
            raise ValueError("optional header extends beyond the artifact")
        optional_magic = int.from_bytes(
            raw[optional_offset : optional_offset + 2], "little"
        )
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
    except (OSError, ValueError) as exc:
        state["reason"] = f"{type(exc).__name__}: {exc}"
    return state


def _verify_native_build_manifest(router_home: Path, native_bin: Path) -> dict:
    """Verify that the loadable binaries bind to this exact source checkout."""
    manifest_path = native_bin / NATIVE_BUILD_MANIFEST_NAME
    receipt = {
        "path": str(manifest_path),
        "sha256": None,
        "valid": False,
        "checks": {},
        "errors": [],
        "artifact_paths": [],
    }
    native_bin_error = _path_reparse_error(native_bin)
    if native_bin_error:
        receipt["errors"].append(
            "native build artifact directory is unsafe: " + native_bin_error
        )
        return receipt
    if not manifest_path.is_file() or _path_reparse_error(manifest_path) is not None:
        receipt["errors"].append("native build manifest is missing or unsafe")
        return receipt
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = _strict_json_loads(manifest_bytes.decode("utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        receipt["errors"].append(
            f"native build manifest is not parseable: {type(exc).__name__}: {exc}"
        )
        return receipt
    receipt["sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    if not isinstance(manifest, dict):
        receipt["errors"].append("native build manifest is not an object")
        return receipt

    checks = receipt["checks"]
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
    checks["load_bin_dir"] = _same_resolved_path(manifest.get("load_bin_dir"), native_bin)
    if not checks["load_bin_dir"]:
        receipt["errors"].append("manifest load bin directory")

    checkout = manifest.get("checkout")
    git = checkout.get("git") if isinstance(checkout, dict) else None
    checks["checkout_root"] = isinstance(checkout, dict) and _same_resolved_path(
        checkout.get("root"), router_home
    )
    if not checks["checkout_root"]:
        receipt["errors"].append("manifest checkout root")
    current_git = _native_source_git_state(router_home)
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
                receipt["errors"].append("manifest " + key.replace("git_", "Git "))

    manifest_recipe = manifest.get("build_recipe")
    current_recipe = _build_recipe_state(router_home)
    checks["build_recipe"] = (
        isinstance(manifest_recipe, dict)
        and manifest_recipe.get("path") == _NATIVE_BUILD_RECIPE_PATH.as_posix()
        and isinstance(manifest_recipe.get("sha256"), str)
        and manifest_recipe.get("sha256").lower() == current_recipe.get("sha256")
        and current_recipe.get("available") is True
    )
    if not checks["build_recipe"]:
        receipt["errors"].append("manifest build recipe SHA-256")

    source_tree = manifest.get("source_tree")
    manifest_inputs = source_tree.get("inputs") if isinstance(source_tree, dict) else None
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
            normalized_inputs.append({"path": path, "sha256": sha256, "bytes": size})
    else:
        normalized_inputs = None
    try:
        actual_inputs = _native_source_inputs(router_home)
    except (OSError, ValueError) as exc:
        actual_inputs = None
        receipt["errors"].append(
            f"native source inventory is unavailable: {type(exc).__name__}: {exc}"
        )
    checks["source_tree"] = (
        isinstance(source_tree, dict)
        and source_tree.get("algorithm") == "sha256"
        and normalized_inputs is not None
        and actual_inputs is not None
        and normalized_inputs == actual_inputs
        and source_tree.get("digest") == _source_tree_digest(actual_inputs)
    )
    if not checks["source_tree"]:
        receipt["errors"].append("native source-tree digest or input inventory")

    artifacts = manifest.get("artifacts")
    by_leaf: dict[str, dict] = {}
    if isinstance(artifacts, list):
        for item in artifacts:
            if isinstance(item, dict) and isinstance(item.get("leaf"), str):
                leaf = item["leaf"]
                if leaf in by_leaf:
                    receipt["errors"].append(f"duplicate manifest artifact: {leaf}")
                by_leaf[leaf] = item
    else:
        receipt["errors"].append("manifest artifacts")
    artifact_paths = []
    artifact_checks = True
    for leaf in DISPLAY_MEMBERSHIP_REQUIRED_ARTIFACTS:
        item = by_leaf.get(leaf)
        path = native_bin / leaf
        observed_pe = _pe64_image_state(path) if path.is_file() else {"verified": False}
        manifest_pe = item.get("pe_verification") if isinstance(item, dict) else None
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
        ok = (
            isinstance(item, dict)
            and item.get("current") is True
            and path.is_file()
            and not _is_reparse_point(path)
            and isinstance(item.get("bytes"), int)
            and not isinstance(item.get("bytes"), bool)
            and item.get("bytes") == path.stat().st_size
            and isinstance(item.get("sha256"), str)
            and item.get("sha256").lower() == _sha256_file(path)
            and pe_ok
        )
        checks[f"artifact_pe:{leaf}"] = pe_ok
        checks[f"artifact:{leaf}"] = ok
        if not ok:
            artifact_checks = False
            receipt["errors"].append(f"manifest artifact binding: {leaf}")
        else:
            artifact_paths.append(path)
    checks["artifacts"] = artifact_checks
    display_membership = manifest.get("display_membership")
    checks["display_membership_ready"] = (
        isinstance(display_membership, dict)
        and display_membership.get("ready") is True
        and display_membership.get("canonical_arx_current") is True
        and by_leaf.get("Ariadne.AcadNative.arx", {}).get("current") is True
    )
    if not checks["display_membership_ready"]:
        receipt["errors"].append("canonical ARX is not current for display membership")
    receipt["artifact_paths"] = [str(path) for path in artifact_paths]
    receipt["valid"] = not receipt["errors"]
    return receipt


def _attended_execution_state(attended: dict) -> dict:
    """Separate a constructed command from evidence that a process actually ran."""
    command = attended.get("command")
    command_constructed = isinstance(command, (list, tuple)) and bool(command)
    envelope = attended.get("envelope")
    receipt_launch = isinstance(envelope, dict) and _is_positive_plain_int(
        envelope.get("launched_pid")
    )
    launch_evidence = "final_receipt.launched_pid" if receipt_launch else "none"
    if not receipt_launch:
        completion_path = attended.get("completion_receipt")
        if isinstance(completion_path, str) and completion_path:
            try:
                completion = _load_json_bom(Path(completion_path))
            except (OSError, UnicodeError, ValueError):
                completion = None
            receipt_launch = (
                isinstance(completion, dict)
                and completion.get("schema")
                == "ariadne.cad_os.attended_job_completion.v1"
                and completion.get("phase") == "cleanup_pending"
                and _is_positive_plain_int(completion.get("launched_pid"))
            )
            if receipt_launch:
                launch_evidence = "completion_receipt.launched_pid"
    return {
        "command_constructed": command_constructed,
        "launch_observed": receipt_launch,
        "launch_evidence": launch_evidence,
    }


def _hash_parts(*parts: object) -> str:
    """WorldIR-compatible stable identity over length-prefixed UTF-8 fields.

    This shares only the identity convention with the WorldIR path. Visibility
    is decided independently by the native ObjectARX operation.
    """
    digest = hashlib.sha256()
    for part in parts:
        raw = str(part).encode("utf-8")
        digest.update(len(raw).to_bytes(8, byteorder="big", signed=False))
        digest.update(raw)
    return digest.hexdigest()


def _import_optional(module_name: str):
    """Import a sibling module that another lane owns; return (mod, error_str|None)."""
    try:
        mod = __import__(module_name)
        return mod, None
    except Exception as exc:  # ImportError or downstream error in that module
        return None, f"{type(exc).__name__}: {exc}"


class Cad:
    """The cadctl control surface. All methods return plain dicts (stateless)."""

    def __init__(self, router_home: Path | str = ROUTER_HOME):
        self.router_home = Path(router_home)
        self.config_dir = self.router_home / "config"
        self.reports_dir = self.router_home / "reports"
        self.status_json = self.reports_dir / "autocad_router_status_latest.json"
        self.staging_golden = self.router_home / "staging" / "golden"

    # ------------------------------------------------------------------ status
    def status(self) -> dict:
        """Read the published router status JSON read-only and normalize it.

        DOES NOT run `-Action status`. If the published file is missing, report
        that truthfully (status='unavailable') rather than spawning a probe.
        """
        if not self.status_json.exists():
            return {
                "schema": "ariadne.cadctl.status.v1",
                "status": "unavailable",
                "reason": f"published router status JSON not found: {self.status_json}",
                "status_json_path": str(self.status_json),
                "route_count": 0,
                "available_count": 0,
                "native_available": False,
            }
        try:
            raw = _load_json_bom(self.status_json)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.status.v1",
                "status": "error",
                "reason": f"failed to parse status JSON: {type(exc).__name__}: {exc}",
                "status_json_path": str(self.status_json),
            }
        native_modules = raw.get("native_modules") or {}
        native_status = str(native_modules.get("status", "")).upper()
        routes = raw.get("routes") or []
        out = {
            "schema": "ariadne.cadctl.status.v1",
            "status": "ok",
            "router_status": raw.get("status"),
            "router_status_schema": raw.get("schema"),
            "status_json_path": str(self.status_json),
            "router_home": raw.get("router_home"),
            "timestamp": raw.get("timestamp"),
            "route_count": raw.get("route_count", len(routes)),
            "available_count": raw.get(
                "available_count",
                sum(1 for r in routes if r.get("available")),
            ),
            "unavailable": list(raw.get("unavailable", []) or []),
            "native_available": native_status == "PASS",
            "native_modules_status": native_modules.get("status"),
            "routes": [
                {"route": r.get("route"), "available": bool(r.get("available")),
                 "engine": r.get("engine")}
                for r in routes
            ],
            "note": "read-only snapshot of the router-published status; not a live probe.",
        }
        reg = self.registry_coverage()
        if reg.get("status") == "ok":
            by_status = reg.get("computed_by_status") or {}
            out["registry"] = {
                "schema": reg.get("registry_schema"),
                "version": reg.get("registry_version"),
                "operation_count": reg.get("operation_count"),
                "implemented": by_status.get("implemented", 0),
                "wired": by_status.get("wired", 0),
                "stub": by_status.get("stub", 0),
                "catalogued": by_status.get("catalogued", 0),
                "blocked": by_status.get("blocked", 0),
                "deprecated": by_status.get("deprecated", 0),
                "unknown": reg.get("unknown_count", 0),
                "consistent": reg.get("consistent"),
            }
        else:
            out["registry"] = {
                "status": reg.get("status"),
                "reason": reg.get("reason"),
                "unknown": None,
            }
        return out

    # ----------------------------------------------------------------- inspect
    def inspect(self, dwg_path: str, out_dir: str, mode: str = "graph",
                include_rich: bool = False) -> dict:
        """Stage a COPY of dwg_path, run the router DWG extraction on the copy,
        normalize to dwg_graph_ir.v1, and write the full artifact set into out_dir.

        include_rich=True routes the native inspect.database.graph op (ObjectARX
        .dbx/.crx) instead of the geometry-only extractor, producing a
        coverage_level="native_full" IR (symbol tables, blocks, layouts, xrefs,
        dictionaries, xrecords) via ir_builder.build_ir_from_database_graph.

        Artifacts written to out_dir:
          cad_job.json        -- the job descriptor we issued
          stdout.txt          -- router stdout (captured)
          stderr.txt          -- router stderr (captured)
          cad_result.json     -- ariadne.autocad_sdk_result.v2
          dwg_graph_ir.json   -- ariadne.dwg_graph_ir.v1 (when extraction succeeded)

        Truthful failure modes:
          - input missing                -> status 'blocked'
          - ir_builder (Lane B3) absent  -> status 'not_implemented'
          - router extraction failed     -> status 'partial' / 'unavailable'
        """
        out_dir_p = Path(out_dir)
        out_dir_p.mkdir(parents=True, exist_ok=True)
        cad_job_path = out_dir_p / "cad_job.json"
        cad_result_path = out_dir_p / "cad_result.json"
        ir_path = out_dir_p / "dwg_graph_ir.json"

        src = Path(dwg_path)
        operation = "inspect.geometry.extract"

        # --- precondition: input exists ---
        if not src.exists():
            cad_job = self._build_cad_job(operation, dwg_path, None, mode)
            cad_job_path.write_text(json.dumps(cad_job, ensure_ascii=False, indent=2), encoding="utf-8")
            result = normalize_result.blocked_result(
                operation, "PRECONDITION_FAILED",
                f"input DWG not found: {dwg_path}", input_path=str(dwg_path),
            )
            result["job_ref"] = str(cad_job_path)
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope("blocked", result, cad_job_path, cad_result_path,
                                          None, None, staged=None,
                                          reason="input DWG not found")

        # --- stage a COPY under staging/golden/<ts>/ (NEVER touch the original) ---
        stage_root = self.staging_golden / _ts()
        stage_root.mkdir(parents=True, exist_ok=True)
        staged = stage_root / "input.dwg"
        shutil.copy2(src, staged)
        try:
            os.chmod(staged, 0o666)  # ensure the staged copy is writable for the lane
        except OSError:
            pass
        staged_meta = {
            "staged_copy": str(staged),
            "original": str(src.resolve()),
            "byte_size": staged.stat().st_size,
            "sha256_16": _sha256_head(staged),
            "staged_at": _now_iso(),
        }

        cad_job = self._build_cad_job(operation, dwg_path, staged_meta, mode)
        cad_job_path.write_text(json.dumps(cad_job, ensure_ascii=False, indent=2), encoding="utf-8")

        # --- rich native_full path: native inspect.database.graph ---
        if include_rich:
            return self._inspect_rich_native(src, staged, staged_meta, out_dir_p,
                                             cad_job_path, cad_result_path, ir_path)

        # --- run the router extraction on the COPY (captures stdout/stderr/exit) ---
        run_res = run_job.run_router_extract(
            str(staged), str(out_dir_p), intent="dwg", extract_mode="geometry_native"
        )
        envelope = run_res.get("envelope")

        # Build the cad_result.v2 from whatever the router returned.
        if envelope is None:
            # Router produced no parseable JSON (missing entrypoint, spawn failure,
            # or timeout). That is unavailable/partial, never ok.
            reason = run_res.get("error") or "router produced no parseable JSON envelope"
            status_word = "unavailable" if run_res.get("error") else "partial"
            code = "HOST_UNAVAILABLE" if run_res.get("error") else "ROUTE_NONZERO_EXIT"
            result = normalize_result.blocked_result(
                operation, code, reason,
                exit_code=run_res.get("exit_code"),
                stdout_ref=run_res.get("stdout_path"),
                stderr_ref=run_res.get("stderr_path"),
            )
            # blocked_result chose status by code; force the intended word.
            result["status"] = status_word
            result["error"]["retryable"] = True
            result["job_ref"] = str(cad_job_path)
            result.setdefault("artifacts", []).append(
                {"kind": "dwg_staged", "ref": str(staged)}
            )
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope(status_word, result, cad_job_path, cad_result_path,
                                          run_res.get("stdout_path"), run_res.get("stderr_path"),
                                          staged=str(staged), reason=reason)

        result = normalize_result.normalize_router_run(
            envelope,
            operation=operation,
            job_ref=str(cad_job_path),
            write_mode="read",
            stdout_ref=run_res.get("stdout_path"),
            stderr_ref=run_res.get("stderr_path"),
        )

        # If the router did not succeed, write the result and stop (no IR).
        if result.get("status") != "ok":
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope(result.get("status", "error"), result,
                                          cad_job_path, cad_result_path,
                                          run_res.get("stdout_path"), run_res.get("stderr_path"),
                                          staged=str(staged),
                                          reason="router extraction did not return ok")

        # --- load the extract JSON the router wrote ---
        extract_ref = result.get("result_ref")
        extract = None
        extract_err = None
        if extract_ref and Path(extract_ref).exists():
            try:
                extract = _load_json_bom(Path(extract_ref))
            except Exception as exc:
                extract_err = f"failed to read extract JSON: {type(exc).__name__}: {exc}"
        else:
            extract_err = f"router reported ok but extract JSON missing: {extract_ref}"

        if extract is None:
            result["status"] = "partial"
            result["error"] = {
                "code": "VALIDATION_ERROR",
                "message": extract_err or "extract unavailable",
                "retryable": False,
            }
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope("partial", result, cad_job_path, cad_result_path,
                                          run_res.get("stdout_path"), run_res.get("stderr_path"),
                                          staged=str(staged), reason=extract_err)

        # --- normalize extract -> dwg_graph_ir.v1 via Lane B3's ir_builder ---
        ir_builder, imp_err = _import_optional("ir_builder")
        if ir_builder is None:
            # ir_builder is owned by Lane B3 and not present yet: report truthfully.
            result["status"] = "not_implemented"
            result["error"] = {
                "code": "OPERATION_NOT_IMPLEMENTED",
                "message": f"ir_builder (Lane B3) unavailable; cannot normalize extract to dwg_graph_ir.v1: {imp_err}",
                "retryable": True,
                "details": {"missing_module": "ir_builder", "extract_ref": extract_ref},
            }
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope("not_implemented", result, cad_job_path, cad_result_path,
                                          run_res.get("stdout_path"), run_res.get("stderr_path"),
                                          staged=str(staged),
                                          reason="ir_builder not available")

        source_meta = {
            "dwg_path": str(staged),
            "original_path": str(src.resolve()),
            "dwg_name": src.name,
            "format": "dwg",
            "byte_size": staged_meta["byte_size"],
            "sha256": _sha256_head(staged, 64).lower(),
            "extractor": (envelope.get("execution") or {}).get("engine_output", {}).get("winning_engine")
            or "objectarx",
            "engine_tier": "native_arx",
            "extracted_at": _now_iso(),
        }
        summary = extract.get("summary")
        try:
            ir = ir_builder.build_ir_from_extract(extract, summary, source_meta)
            ir_written = ir_builder.write_ir(ir, str(ir_path))
        except Exception as exc:
            result["status"] = "partial"
            result["error"] = {
                "code": "VALIDATION_ERROR",
                "message": f"ir_builder.build_ir_from_extract failed: {type(exc).__name__}: {exc}",
                "retryable": False,
                "details": {"extract_ref": extract_ref},
            }
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope("partial", result, cad_job_path, cad_result_path,
                                          run_res.get("stdout_path"), run_res.get("stderr_path"),
                                          staged=str(staged), reason="ir_builder failed")

        # --- success: attach IR ref + diagnostics, finalize cad_result.v2 ---
        ir_diag = (ir or {}).get("diagnostics", {})
        result["ir_ref"] = str(ir_path)
        result.setdefault("diagnostics", {})["entity_count"] = ir_diag.get("entity_count")
        result.setdefault("artifacts", []).append({"kind": "ir", "ref": str(ir_path)})
        cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        return self._inspect_envelope("ok", result, cad_job_path, cad_result_path,
                                      run_res.get("stdout_path"), run_res.get("stderr_path"),
                                      staged=str(staged), ir_path=str(ir_path),
                                      entity_count=ir_diag.get("entity_count"),
                                      reason=None)

    def _inspect_rich_native(self, src: Path, staged: Path, staged_meta: dict,
                             out_dir_p: Path, cad_job_path: Path,
                             cad_result_path: Path, ir_path: Path) -> dict:
        """Native inspect.database.graph -> coverage_level=native_full IR."""
        operation = "inspect.database.graph"
        # overwrite the cad_job with the rich operation for accuracy
        cad_job = self._build_cad_job(operation, str(src), staged_meta, "graph")
        cad_job_path.write_text(json.dumps(cad_job, ensure_ascii=False, indent=2), encoding="utf-8")

        run_res = run_job.run_router_cad_job(
            str(staged), str(out_dir_p), operation, write_mode="read")
        stdout_path = run_res.get("stdout_path")
        stderr_path = run_res.get("stderr_path")
        result_obj = run_res.get("result")

        if result_obj is None:
            reason = run_res.get("error") or "native graph job produced no result JSON"
            status_word = "unavailable" if run_res.get("error") else "partial"
            code = "HOST_UNAVAILABLE" if run_res.get("error") else "ROUTE_NONZERO_EXIT"
            result = normalize_result.blocked_result(
                operation, code, reason, exit_code=run_res.get("exit_code"),
                stdout_ref=stdout_path, stderr_ref=stderr_path)
            result["status"] = status_word
            result["job_ref"] = str(cad_job_path)
            result.setdefault("artifacts", []).append({"kind": "dwg_staged", "ref": str(staged)})
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope(status_word, result, cad_job_path, cad_result_path,
                                          stdout_path, stderr_path, staged=str(staged), reason=reason)

        ir_builder, imp_err = _import_optional("ir_builder")
        if ir_builder is None or not hasattr(ir_builder, "build_ir_from_database_graph"):
            result = normalize_result.blocked_result(
                operation, "OPERATION_NOT_IMPLEMENTED",
                f"ir_builder.build_ir_from_database_graph unavailable: {imp_err}",
                result_json=run_res.get("result_json"))
            result["status"] = "not_implemented"
            result["job_ref"] = str(cad_job_path)
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope("not_implemented", result, cad_job_path, cad_result_path,
                                          stdout_path, stderr_path, staged=str(staged),
                                          reason="ir_builder rich builder not available")

        source_meta = {
            "dwg_path": str(staged),
            "original_path": str(src.resolve()),
            "dwg_name": src.name,
            "format": "dwg",
            "byte_size": staged_meta["byte_size"],
            "sha256": _sha256_head(staged, 64).lower(),
            "extractor": "native_objectarx",
            "engine_tier": "native_arx",
            "route": "dwg_truth_autocad",
            "extracted_at": _now_iso(),
        }
        try:
            ir = ir_builder.build_ir_from_database_graph(result_obj, source_meta)
            ir_builder.write_ir(ir, str(ir_path))
        except Exception as exc:
            result = normalize_result.blocked_result(
                operation, "VALIDATION_ERROR",
                f"build_ir_from_database_graph failed: {type(exc).__name__}: {exc}",
                result_json=run_res.get("result_json"))
            result["status"] = "partial"
            result["job_ref"] = str(cad_job_path)
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope("partial", result, cad_job_path, cad_result_path,
                                          stdout_path, stderr_path, staged=str(staged),
                                          reason="rich IR build failed")

        diag = ir.get("diagnostics", {})
        result = {
            "schema": "ariadne.autocad_sdk_result.v2",
            "operation": operation,
            "status": "ok",
            "write_mode": "read",
            "job_ref": str(cad_job_path),
            "result_ref": run_res.get("result_json"),
            "ir_ref": str(ir_path),
            "diagnostics": {
                "entity_count": diag.get("entity_count"),
                "coverage_level": ir.get("coverage_level"),
                "sections_present": (diag.get("coverage") or {}).get("sections_present"),
            },
            "artifacts": [
                {"kind": "ir", "ref": str(ir_path)},
                {"kind": "dwg_staged", "ref": str(staged)},
            ],
        }
        cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return self._inspect_envelope("ok", result, cad_job_path, cad_result_path,
                                      stdout_path, stderr_path, staged=str(staged),
                                      ir_path=str(ir_path), entity_count=diag.get("entity_count"),
                                      reason=None)

    # ------------------------------------------------------------------- query
    def query(self, ir_path: str, sql: str) -> dict:
        """Run a read-only SQL query against an IR's sqlite store (Lane B2).

        Builds an ephemeral sqlite DB from the IR via sqlite_ir_store.build_store,
        then runs sqlite_ir_store.query(db, sql). Truthful failures: ir missing ->
        blocked; sqlite_ir_store (Lane B2) absent -> not_implemented.
        """
        irp = Path(ir_path)
        if not irp.exists():
            return {
                "schema": "ariadne.cadctl.query.v1",
                "status": "blocked",
                "reason": f"IR file not found: {ir_path}",
            }
        store, imp_err = _import_optional("sqlite_ir_store")
        if store is None:
            return {
                "schema": "ariadne.cadctl.query.v1",
                "status": "not_implemented",
                "reason": f"sqlite_ir_store (Lane B2) unavailable: {imp_err}",
            }
        try:
            ir = _load_json_bom(irp)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.query.v1",
                "status": "error",
                "reason": f"failed to read IR: {type(exc).__name__}: {exc}",
            }
        # Build the store next to the IR (deterministic, overwritable).
        db_path = str(irp.with_suffix(".sqlite"))
        try:
            build_info = store.build_store(ir, db_path)
            result = store.query(db_path, sql)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.query.v1",
                "status": "error",
                "reason": f"sqlite_ir_store failed: {type(exc).__name__}: {exc}",
                "db_path": db_path,
            }
        return {
            "schema": "ariadne.cadctl.query.v1",
            "status": "ok",
            "db_path": db_path,
            "store": build_info,
            "columns": result.get("columns", []),
            "rows": result.get("rows", []),
            "row_count": len(result.get("rows", [])),
        }

    def get_entity(self, ir_path: str, handle: str) -> dict:
        """Fetch one entity by handle using the same read-only SQL shell."""
        safe_handle = str(handle).replace("'", "''")
        q = self.query(ir_path, "SELECT * FROM entities WHERE handle = '%s'" % safe_handle)
        if q.get("status") != "ok":
            return {
                "schema": "ariadne.cadctl.get_entity.v1",
                "status": q.get("status", "error"),
                "handle": handle,
                "reason": q.get("reason") or q.get("error"),
                "delegate": "cadctl.query",
            }
        return {
            "schema": "ariadne.cadctl.get_entity.v1",
            "status": "ok",
            "handle": handle,
            "db_path": q.get("db_path"),
            "columns": q.get("columns", []),
            "rows": q.get("rows", []),
            "row_count": q.get("row_count", 0),
            "delegate": "cadctl.query",
        }

    # ---------------------------------------------------------------- validate
    def validate(self, ir_path: str) -> dict:
        """Validate an IR/run via the deterministic gates in validator (Lane E).

        Truthful failure: validator absent -> not_implemented (NOT a faked pass).
        """
        irp = Path(ir_path)
        if not irp.exists():
            return {
                "schema": "ariadne.cadctl.validate.v1",
                "status": "blocked",
                "reason": f"IR file not found: {ir_path}",
            }
        validator, imp_err = _import_optional("validator")
        if validator is None:
            return {
                "schema": "ariadne.cadctl.validate.v1",
                "status": "not_implemented",
                "reason": f"validator (Lane E) unavailable: {imp_err}",
            }
        try:
            report = validator.validate_target(ir_path=str(irp), run_dir=str(irp.parent))
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.validate.v1",
                "status": "error",
                "reason": f"validator.validate_target failed: {type(exc).__name__}: {exc}",
            }
        return {
            "schema": "ariadne.cadctl.validate.v1",
            "status": "ok",
            "report": report,
        }

    # --------------------------------------------------------------- registry
    def registry_list(self) -> dict:
        """List the v2 operation registry (config/operations.v2.json, utf-8-sig)."""
        if not OPERATIONS_V2.exists():
            return {
                "schema": "ariadne.cadctl.registry_list.v1",
                "status": "unavailable",
                "reason": f"operations.v2.json not found: {OPERATIONS_V2}",
            }
        reg = _load_json_bom(OPERATIONS_V2)
        ops = reg.get("operations", []) or []
        listed = [
            {
                "id": o.get("id"),
                "family": o.get("family"),
                "status": o.get("status"),
                "engine_tier": o.get("engine_tier"),
                "router_lane": (o.get("handler") or {}).get("router_lane"),
                "execution_host_class": (o.get("handler") or {}).get("execution_host_class"),
            }
            for o in ops
        ]
        return {
            "schema": "ariadne.cadctl.registry_list.v1",
            "status": "ok",
            "registry_schema": reg.get("schema"),
            "registry_version": reg.get("version"),
            "operation_count": len(listed),
            "wired_count": sum(1 for o in listed if o["status"] == "implemented"),
            "operations": listed,
        }

    def registry_coverage(self) -> dict:
        """Summarize operation coverage (totals + coverage block of operations.v2)."""
        if not OPERATIONS_V2.exists():
            return {
                "schema": "ariadne.cadctl.registry_coverage.v1",
                "status": "unavailable",
                "reason": f"operations.v2.json not found: {OPERATIONS_V2}",
            }
        reg = _load_json_bom(OPERATIONS_V2)
        ops = reg.get("operations", []) or []
        by_status: dict = {}
        by_family: dict = {}
        by_tier: dict = {}
        for o in ops:
            by_status[o.get("status")] = by_status.get(o.get("status"), 0) + 1
            by_family[o.get("family")] = by_family.get(o.get("family"), 0) + 1
            by_tier[o.get("engine_tier")] = by_tier.get(o.get("engine_tier"), 0) + 1
        wired = by_status.get("implemented", 0)
        unknown_count = sum(v for k, v in by_status.items() if k in (None, "", "unknown"))
        return {
            "schema": "ariadne.cadctl.registry_coverage.v1",
            "status": "ok",
            "registry_schema": reg.get("schema"),
            "registry_version": reg.get("version"),
            "operation_count": len(ops),
            "wired_count": wired,
            "totals": reg.get("totals"),
            "declared_coverage": reg.get("coverage"),
            "computed_by_status": by_status,
            "computed_by_family": by_family,
            "computed_by_engine_tier": by_tier,
            "unknown_count": unknown_count,
            "consistent": (
                reg.get("totals", {}).get("by_status", {}).get("implemented") == wired
            ),
        }

    def registry_explain(self, op_id: str) -> dict:
        """Return the full v2 registry record for one operation (drives `explain`)."""
        if not OPERATIONS_V2.exists():
            return {
                "schema": "ariadne.cadctl.registry_explain.v1",
                "status": "unavailable",
                "reason": f"operations.v2.json not found: {OPERATIONS_V2}",
            }
        reg = _load_json_bom(OPERATIONS_V2)
        ops = reg.get("operations", []) or []
        rec = next((o for o in ops if o.get("id") == op_id), None)
        if rec is None:
            return {
                "schema": "ariadne.cadctl.registry_explain.v1",
                "status": "not_found",
                "operation": op_id,
                "reason": f"operation '{op_id}' not found in registry",
                "known_count": len(ops),
            }
        return {
            "schema": "ariadne.cadctl.registry_explain.v1",
            "status": "ok",
            "operation": op_id,
            "registry_operation_status": rec.get("status"),
            "record": rec,
        }

    def _registry_operation_status(self, op_id: str | None) -> str | None:
        if not op_id:
            return None
        rec = self._registry_record(op_id)
        return rec.get("status") if rec else None

    def _registry_record(self, op_id: str | None) -> dict | None:
        """Return the full v2 registry record for op_id (by 'id' or 'operation'), or None."""
        if not op_id:
            return None
        try:
            reg = _load_json_bom(OPERATIONS_V2)
        except Exception:
            return None
        for rec in reg.get("operations", []) or []:
            if rec.get("id") == op_id or rec.get("operation") == op_id:
                return rec
        return None

    def _run_op_refusal(self, op_id, status_word, reason, out_dir,
                        registry_status=None, blocked_reason=None) -> dict:
        env = {
            "schema": "ariadne.cadctl.run_operation.v1",
            "operation": op_id,
            "status": status_word,
            "executed": False,
            "registry_operation_status": registry_status,
            "reason": reason,
            "out_dir": str(out_dir),
        }
        if blocked_reason:
            env["registry_blocked_reason"] = blocked_reason
        return env

    # ------------------------------------------------------------- run_operation
    def run_operation(self, op_id: str, args: dict | None = None,
                      write_mode: str | None = None, dwg_path: str | None = None,
                      out_dir: str | None = None) -> dict:
        """Drive ANY implemented registry operation through the native router job lane.

        The generic agent-control entry point: maps an arbitrary op_id onto the
        ObjectARX native-job lane (the same lane inspect.database.graph uses),
        behind a registry allow-list + write-mode governance gate.

        Safety gates (no-fake / original-safe):
          * op_id must be status=='implemented'. blocked / unknown / not-found ->
            truthful refusal (executed=False); the op is NEVER run.
          * write-mode governance: defaults to the op's registry default_write_mode;
            an explicit write_mode must be in allowed_write_modes; write_original is
            ALWAYS refused from this surface (the original DWG stays READ-ONLY).
          * a COPY is staged; the original DWG's sha is verified unchanged.

        Staged-copy snapshot (pre/post, for run-record-only verification):
          the router (autocad-router.ps1 -> Invoke-CadJobRoute) stages its OWN,
          second-level copy under staging/dwg_job_<stamp>/ and _QSAVEs THAT one
          for write ops; the copy staged here (`staged_copy`) is never touched
          again, so its sha256 taken right before the router runs is a true
          pre-write snapshot. The router's own post-run copy is reported back
          as run_res["staged_used"]; its path + sha256 are surfaced here as
          `staged_result` / `staged_result_sha256` so a caller can verify what a
          write op actually produced from this record alone, without re-deriving
          anything. read-mode ops never _QSAVE, so `staged_result_sha256` equals
          `staged_copy_sha256` in that case.
        """
        out_dir_p = Path(out_dir) if out_dir else (self.router_home / "runs" / "run_op" / _ts())
        out_dir_p.mkdir(parents=True, exist_ok=True)

        # --- registry allow-list gate ---
        rec = self._registry_record(op_id)
        if rec is None:
            return self._run_op_refusal(op_id, "not_found",
                f"operation '{op_id}' is not in the operation registry", out_dir_p)
        op_status = rec.get("status")
        if op_status != "implemented":
            return self._run_op_refusal(op_id, "blocked",
                f"operation '{op_id}' has registry status '{op_status}', not 'implemented'; refused",
                out_dir_p, registry_status=op_status, blocked_reason=rec.get("blocked_reason"))

        # --- write-mode governance ---
        wl = rec.get("write_level") or {}
        default_wm = wl.get("default_write_mode") or "read"
        allowed = set(wl.get("allowed_write_modes") or [default_wm])
        wm = write_mode or default_wm
        if wm in ("write_original", "original"):
            return self._run_op_refusal(op_id, "blocked",
                "write_mode 'write_original' is never permitted from the agent run surface; "
                "the original DWG is READ-ONLY (use a staged write_copy)",
                out_dir_p, registry_status=op_status)
        if wm not in allowed:
            return self._run_op_refusal(op_id, "blocked",
                f"write_mode '{wm}' is not in allowed_write_modes {sorted(allowed)} for '{op_id}'",
                out_dir_p, registry_status=op_status)

        # --- stage the input DWG (original READ-ONLY) ---
        if not dwg_path:
            return self._run_op_refusal(op_id, "blocked",
                "run_operation requires a dwg_path (a copy is staged); no-input generator ops "
                "are not yet wired through this surface",
                out_dir_p, registry_status=op_status)
        src = Path(dwg_path)
        if not src.exists():
            return self._run_op_refusal(op_id, "blocked",
                f"input DWG not found: {dwg_path}", out_dir_p, registry_status=op_status)
        original_sha256_before = _sha256_head(src, 64).lower()
        stage_root = self.staging_golden / _ts()
        stage_root.mkdir(parents=True, exist_ok=True)
        staged = stage_root / "input.dwg"
        shutil.copy2(src, staged)
        try:
            os.chmod(staged, 0o666)
        except OSError:
            pass
        # Staged-copy semantics (envelope truth contract):
        #   staged_copy        = cadctl's pristine pre-op copy; sha MUST equal the
        #                        original and MUST stay byte-identical through the run
        #                        (the router re-stages into its own dwg_job_* file).
        #   staged_copy_sha256 = full sha256 of staged_copy captured NOW (pre-router).
        #   staged_result      = router-reported post-op file (run_res["staged_used"]);
        #                        for write_copy this is the post-_QSAVE artifact; for
        #                        read it is the router's unmutated second-level copy.
        #   staged_result_sha256 = full sha256 of staged_result after the router returns.
        staged_copy_sha256 = _sha256_head(staged, 64).lower()
        staged_copy_matches_original = (staged_copy_sha256 == original_sha256_before)
        if not staged_copy_matches_original:
            return {
                "schema": "ariadne.cadctl.run_operation.v1",
                "operation": op_id,
                "status": "error",
                "executed": False,
                "registry_operation_status": op_status,
                "write_mode": wm,
                "out_dir": str(out_dir_p),
                "staged_copy": str(staged),
                "staged_copy_sha256": staged_copy_sha256,
                "original_sha256_before": original_sha256_before,
                "staged_copy_matches_original": False,
                "reason": "SAFETY VIOLATION: staged copy sha does not match original at staging time",
            }

        # --- optional args -> ARIADNE_NATIVE_JOB job file (-JobPath) ---
        job_path = None
        if args:
            job_path = str(out_dir_p / "job_args.json")
            payload = {"operation": op_id}
            payload.update(args)
            Path(job_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        # --- drive the native job lane on the COPY ---
        run_res = run_job.run_router_cad_job(str(staged), str(out_dir_p), op_id,
                                             write_mode=wm, job_path=job_path)
        original_sha256_after = _sha256_head(src, 64).lower()
        original_unchanged = (original_sha256_before == original_sha256_after)
        # Re-read cadctl's staged_copy AFTER the router: if bytes drifted, the path
        # alone would mislead consumers ("staged_copy=pre-write" ambiguity).
        staged_copy_sha_after = _sha256_head(staged, 64).lower()
        staged_copy_unchanged = (staged_copy_sha_after == staged_copy_sha256)

        # Post-run snapshot: the router's own staged copy, reported back as
        # staged_used (engine_output.input). For write ops this is the mutated
        # (post-_QSAVE) file; for read ops it is the router's unmutated read copy.
        staged_result = run_res.get("staged_used")
        staged_result_sha256 = None
        if isinstance(staged_result, str) and staged_result and Path(staged_result).is_file():
            staged_result_sha256 = _sha256_head(Path(staged_result), 64).lower()

        env = {
            "schema": "ariadne.cadctl.run_operation.v1",
            "operation": op_id,
            "executed": True,
            "registry_operation_status": op_status,
            "write_mode": wm,
            "out_dir": str(out_dir_p),
            "staged_copy": str(staged),
            "staged_copy_sha256": staged_copy_sha256,
            "staged_copy_matches_original": staged_copy_matches_original,
            "staged_copy_unchanged": staged_copy_unchanged,
            "staged_result": staged_result,
            "staged_result_sha256": staged_result_sha256,
            "original_sha256_before": original_sha256_before,
            "original_sha256_after": original_sha256_after,
            "original_unchanged": original_unchanged,
            "exit_code": run_res.get("exit_code"),
            "stdout": run_res.get("stdout_path"),
            "stderr": run_res.get("stderr_path"),
            "result_ref": run_res.get("result_json"),
        }
        if not original_unchanged:
            env["status"] = "error"
            env["reason"] = "SAFETY VIOLATION: original DWG sha changed during run_operation"
            return env
        if not staged_copy_unchanged:
            env["status"] = "error"
            env["reason"] = (
                "SAFETY VIOLATION: cadctl staged_copy bytes changed during run; "
                "staged_copy_sha256 is the pre-write snapshot only"
            )
            return env
        if run_res.get("error"):
            env["status"] = "unavailable"
            env["reason"] = run_res.get("error")
            return env
        result_obj = run_res.get("result")
        if result_obj is None:
            env["status"] = "partial"
            env["reason"] = "native job produced no parseable result JSON"
            return env
        native_status = (result_obj.get("status") if isinstance(result_obj, dict) else None) or "ok"
        env["status"] = native_status if native_status in (
            "ok", "blocked", "not_implemented", "partial", "error", "unavailable") else "ok"
        env["result"] = result_obj
        return env

    # ----------------------------------------------------- run_command_template
    def run_command_template(self, template_id: str, slots: dict,
                             dwg: str | None = None, *,
                             timeout_sec: float | None = None) -> dict:
        """Run a governed built-in-command template through W5-TMPL.

        The command_template_engine owns the closed template registry, hostile
        slot gate, typed validation, accoreconsole resolution, staged-copy run,
        and original-sha verification. This surface only refuses unknown
        template ids up front and normalizes the engine result for agents.
        """
        env = {
            "schema": "ariadne.cadctl.run_command_template.v1",
            "template_id": template_id,
            "executed": False,
            "staged_copy": None,
            "original_unchanged": None,
        }
        command_template_engine, imp_err = _import_optional("command_template_engine")
        if command_template_engine is None:
            env.update({
                "status": "not_implemented",
                "reason": f"command_template_engine unavailable: {imp_err}",
            })
            return env
        if slots is None:
            slot_values = {}
        elif isinstance(slots, dict):
            slot_values = slots
        else:
            env.update({
                "status": "blocked",
                "reason": "slots must be a dict of typed template slot values",
            })
            return env

        templates_path = self.config_dir / "command_templates.json"
        try:
            templates = command_template_engine.load_templates(templates_path)
        except Exception as exc:  # registry/parsing errors are refusals, not crashes
            code = getattr(exc, "code", type(exc).__name__)
            env.update({
                "status": "error",
                "reason": f"failed to load command templates: {type(exc).__name__}: {exc}",
                "error": {
                    "code": code,
                    "message": str(exc),
                    "retryable": False,
                },
            })
            return env

        template = templates.get(template_id)
        if template is None:
            env.update({
                "status": "not_found",
                "reason": f"template '{template_id}' is not in command_templates.json",
            })
            return env
        if not dwg:
            env.update({
                "status": "blocked",
                "reason": "run_command_template requires a dwg path (a copy is staged)",
            })
            return env

        write_mode = (template.get("write_mode") or {}).get("default") or "read"
        _tmpl_kw = {} if timeout_sec is None else {"timeout_sec": timeout_sec}
        try:
            result = command_template_engine.run_template(
                template_id,
                slot_values,
                dwg,
                write_mode=write_mode,
                templates_path=templates_path,
                **_tmpl_kw,
            )
        except Exception as exc:
            env.update({
                "status": "error",
                "reason": f"command_template_engine.run_template failed: {type(exc).__name__}: {exc}",
                "error": {
                    "code": type(exc).__name__,
                    "message": str(exc),
                    "retryable": False,
                },
            })
            return env

        diagnostics = result.get("diagnostics") if isinstance(result, dict) else {}
        diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
        details = result.get("details") if isinstance(result, dict) else {}
        if not isinstance(details, dict):
            details = {}
        if not details:
            err = result.get("error") if isinstance(result, dict) else {}
            err_details = err.get("details") if isinstance(err, dict) else {}
            if isinstance(err_details, dict):
                details = err_details

        staged_copy = details.get("staged_input")
        original_unchanged = details.get("original_unchanged")
        env.update({
            "status": result.get("status", "error") if isinstance(result, dict) else "error",
            "executed": bool(staged_copy),
            "write_mode": result.get("write_mode", write_mode) if isinstance(result, dict) else write_mode,
            "staged_copy": staged_copy,
            "original_unchanged": original_unchanged,
            "stdout": diagnostics.get("stdout_ref"),
            "stderr": diagnostics.get("stderr_ref"),
            "result": result,
        })
        err = result.get("error") if isinstance(result, dict) else None
        if isinstance(err, dict):
            env["reason"] = err.get("message")
            env["error"] = err
        return env

    # ------------------------------------------------------------- shell tools
    def patch_dry_run(self, patch: dict) -> dict:
        patch_engine, imp_err = _import_optional("patch_engine")
        if patch_engine is None or not hasattr(patch_engine, "dry_run_plan"):
            return {
                "schema": "ariadne.cadctl.patch_dry_run.v1",
                "status": "not_implemented",
                "reason": f"patch_engine.dry_run_plan unavailable: {imp_err}",
            }
        try:
            return patch_engine.dry_run_plan(patch)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.patch_dry_run.v1",
                "status": "error",
                "reason": f"patch_engine.dry_run_plan failed: {type(exc).__name__}: {exc}",
            }

    def patch_apply_staged(self, patch: dict, dwg_path: str, out_dir: str) -> dict:
        """Apply a cad_patch.v1 to a staged copy through patch_engine.

        This is the explicit M05 mutation surface. It delegates to
        patch_engine.apply_staged, which copies dwg_path to out_dir first and
        never writes the original DWG.
        """
        patch_engine, imp_err = _import_optional("patch_engine")
        if patch_engine is None or not hasattr(patch_engine, "apply_staged"):
            return {
                "schema": "ariadne.cad_patch.result.v1",
                "status": "not_implemented",
                "reason": f"patch_engine.apply_staged unavailable: {imp_err}",
            }
        try:
            return patch_engine.apply_staged(patch, dwg_path, out_dir)
        except Exception as exc:
            return {
                "schema": "ariadne.cad_patch.result.v1",
                "status": "error",
                "reason": f"patch_engine.apply_staged failed: {type(exc).__name__}: {exc}",
            }

    # ------------------------------------------------------------- semantic anchors (W5-ANCHOR)

    def anchor_set(self, dwg_path: str, handle: str, body: dict, out_dir: str, *,
                  author_agent: str, tags: list | None = None) -> dict:
        """Write (upsert) a semantic anchor onto ``handle`` on a STAGED copy of
        ``dwg_path``, via the existing set_entity_xdata_by_handle patch op
        (native modify.entity.xdata -- no new native op). See
        docs/SEMANTIC_ANCHOR_SPEC.md and tools/anchor_ops.py.
        """
        anchor_ops, imp_err = _import_optional("anchor_ops")
        if anchor_ops is None:
            return {
                "schema": "ariadne.cadctl.anchor_set.v1",
                "status": "not_implemented",
                "reason": f"anchor_ops (Lane W5-ANCHOR) unavailable: {imp_err}",
            }
        try:
            patch = anchor_ops.build_anchor_set_patch(
                handle, body, author_agent=author_agent, tags=tags)
        except anchor_ops.AnchorError as exc:
            return {
                "schema": "ariadne.cadctl.anchor_set.v1",
                "status": "blocked",
                "handle": handle,
                "reason": str(exc),
            }
        patch_engine, imp_err2 = _import_optional("patch_engine")
        if patch_engine is None or not hasattr(patch_engine, "apply_staged"):
            return {
                "schema": "ariadne.cadctl.anchor_set.v1",
                "status": "not_implemented",
                "reason": f"patch_engine.apply_staged unavailable: {imp_err2}",
            }
        try:
            patch_result = patch_engine.apply_staged(patch, dwg_path, out_dir)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.anchor_set.v1",
                "status": "error",
                "handle": handle,
                "reason": f"patch_engine.apply_staged failed: {type(exc).__name__}: {exc}",
            }
        return {
            "schema": "ariadne.cadctl.anchor_set.v1",
            "status": patch_result.get("status"),
            "handle": handle,
            "patch_result": patch_result,
        }

    def anchor_clear(self, dwg_path: str, handle: str, out_dir: str, *,
                     author_agent: str) -> dict:
        """Logically clear (tombstone) the semantic anchor on ``handle`` on a
        STAGED copy of ``dwg_path``. KNOWN LIMITATION: this cannot truly
        remove the RegApp xdata (the native handler rejects an empty
        'values' array) -- see anchor_ops.build_anchor_clear_patch and
        docs/SEMANTIC_ANCHOR_SPEC.md "Clear semantics".
        """
        anchor_ops, imp_err = _import_optional("anchor_ops")
        if anchor_ops is None:
            return {
                "schema": "ariadne.cadctl.anchor_clear.v1",
                "status": "not_implemented",
                "reason": f"anchor_ops (Lane W5-ANCHOR) unavailable: {imp_err}",
            }
        try:
            patch = anchor_ops.build_anchor_clear_patch(handle, author_agent=author_agent)
        except anchor_ops.AnchorError as exc:
            return {
                "schema": "ariadne.cadctl.anchor_clear.v1",
                "status": "blocked",
                "handle": handle,
                "reason": str(exc),
            }
        patch_engine, imp_err2 = _import_optional("patch_engine")
        if patch_engine is None or not hasattr(patch_engine, "apply_staged"):
            return {
                "schema": "ariadne.cadctl.anchor_clear.v1",
                "status": "not_implemented",
                "reason": f"patch_engine.apply_staged unavailable: {imp_err2}",
            }
        try:
            patch_result = patch_engine.apply_staged(patch, dwg_path, out_dir)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.anchor_clear.v1",
                "status": "error",
                "handle": handle,
                "reason": f"patch_engine.apply_staged failed: {type(exc).__name__}: {exc}",
            }
        return {
            "schema": "ariadne.cadctl.anchor_clear.v1",
            "status": patch_result.get("status"),
            "handle": handle,
            "patch_result": patch_result,
        }

    def anchor_get(self, ir_path: str, handle: str) -> dict:
        """Read a semantic anchor back from an already-extracted IR (same
        ir_path convention as query()/get_entity()). No native call: xdata is
        already carried through by the existing extraction pipeline.
        """
        irp = Path(ir_path)
        if not irp.exists():
            return {
                "schema": "ariadne.cadctl.anchor_get.v1",
                "status": "blocked",
                "reason": f"IR file not found: {ir_path}",
            }
        anchor_ops, imp_err = _import_optional("anchor_ops")
        if anchor_ops is None:
            return {
                "schema": "ariadne.cadctl.anchor_get.v1",
                "status": "not_implemented",
                "reason": f"anchor_ops (Lane W5-ANCHOR) unavailable: {imp_err}",
            }
        try:
            ir = _load_json_bom(irp)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.anchor_get.v1",
                "status": "error",
                "reason": f"failed to read IR: {type(exc).__name__}: {exc}",
            }
        result = dict(anchor_ops.get_anchor_from_ir(ir, handle))
        result["schema"] = "ariadne.cadctl.anchor_get.v1"
        return result

    def anchor_list(self, ir_path: str) -> dict:
        """List every live (non-tombstoned) semantic anchor in an
        already-extracted IR (same ir_path convention as query()/anchor_get()).
        """
        irp = Path(ir_path)
        if not irp.exists():
            return {
                "schema": "ariadne.cadctl.anchor_list.v1",
                "status": "blocked",
                "reason": f"IR file not found: {ir_path}",
            }
        anchor_ops, imp_err = _import_optional("anchor_ops")
        if anchor_ops is None:
            return {
                "schema": "ariadne.cadctl.anchor_list.v1",
                "status": "not_implemented",
                "reason": f"anchor_ops (Lane W5-ANCHOR) unavailable: {imp_err}",
            }
        try:
            ir = _load_json_bom(irp)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.anchor_list.v1",
                "status": "error",
                "reason": f"failed to read IR: {type(exc).__name__}: {exc}",
            }
        result = dict(anchor_ops.list_anchors_from_ir(ir))
        result["schema"] = "ariadne.cadctl.anchor_list.v1"
        return result

    def diff_before_after(self, pre_ir_path: str, post_ir_path: str) -> dict:
        pre = Path(pre_ir_path)
        post = Path(post_ir_path)
        if not pre.exists() or not post.exists():
            return {
                "schema": "ariadne.cad_diff.v1",
                "status": "blocked",
                "reason": "pre_ir or post_ir file not found",
                "pre_ir": str(pre_ir_path),
                "post_ir": str(post_ir_path),
            }
        cad_diff, imp_err = _import_optional("cad_diff")
        if cad_diff is None or not hasattr(cad_diff, "compute_diff"):
            return {
                "schema": "ariadne.cad_diff.v1",
                "status": "not_implemented",
                "reason": f"cad_diff.compute_diff unavailable: {imp_err}",
            }
        try:
            pre_doc = _load_json_bom(pre)
            post_doc = _load_json_bom(post)
            return cad_diff.compute_diff(pre_doc, post_doc)
        except Exception as exc:
            return {
                "schema": "ariadne.cad_diff.v1",
                "status": "error",
                "reason": f"cad_diff.compute_diff failed: {type(exc).__name__}: {exc}",
            }

    def visual_report(self, source_ref: str, kind: str = "png",
                      artifact_id: str | None = None, out_dir: str | None = None,
                      route: str | None = None) -> dict:
        visual_report, imp_err = _import_optional("visual_report")
        if visual_report is None or not hasattr(visual_report, "build_visual_report"):
            return {
                "schema": "ariadne.visual_artifact.v1",
                "status": "not_implemented",
                "reason": f"visual_report.build_visual_report unavailable: {imp_err}",
            }
        try:
            result = visual_report.build_visual_report(
                source_ref, kind=kind, artifact_id=artifact_id,
                out_dir=out_dir, route=route)
            if result.get("status") == "error" and not Path(source_ref).exists():
                result = dict(result)
                result["status"] = "blocked"
                result["reason"] = "source_ref not found"
            return result
        except Exception as exc:
            return {
                "schema": "ariadne.visual_artifact.v1",
                "status": "error",
                "reason": f"visual_report.build_visual_report failed: {type(exc).__name__}: {exc}",
            }

    def inspect_display_membership(
        self,
        dwg_path: str,
        target_layers: list[str],
        out_dir: str | None = None,
        *,
        geometry_scope: str = DISPLAY_MEMBERSHIP_STRICT_LAYER_ENTITIES_V1,
        timeout: int = 240,
    ) -> dict:
        """Resolve target segment membership through a dedicated full AutoCAD.

        This experiment-only path never falls back to accoreconsole. It stages a
        copy, loads the ARX built from this exact checkout, runs
        ``e2.inspect.xclip_membership``, verifies the original hash, and converts
        only a complete native result into the hash-bound E2 target-oracle schema.
        The default strict scope rejects every curved or unsupported target entity;
        ``linear_segments_v1`` instead admits only linear source segments and
        accounts for the excluded candidates in native evidence.
        """
        requested_out_dir = Path(out_dir) if out_dir else (
            self.router_home / "runs" / "display_membership" / _ts()
        )
        out_dir_p = Path(os.path.abspath(str(requested_out_dir)))
        out_dir_existed = os.path.lexists(out_dir_p)
        output_validation = _validate_display_output_dir(out_dir_p, self.router_home)
        if not output_validation.get("valid"):
            return {
                "schema": "ariadne.cadctl.display_membership.v1",
                "status": "BLOCKED",
                "reason": "unsafe display-membership output directory: "
                + str(output_validation.get("reason")),
                "executed": False,
                "execution_context": "dedicated_full_autocad",
                "operation": "e2.inspect.xclip_membership",
                "out_dir": str(out_dir_p),
                "geometry_scope": geometry_scope,
                "output_validation": output_validation,
            }
        try:
            out_dir_p.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {
                "schema": "ariadne.cadctl.display_membership.v1",
                "status": "BLOCKED",
                "reason": f"cannot create display-membership output directory: {type(exc).__name__}: {exc}",
                "executed": False,
                "execution_context": "dedicated_full_autocad",
                "operation": "e2.inspect.xclip_membership",
                "out_dir": str(out_dir_p),
                "geometry_scope": geometry_scope,
                "output_validation": output_validation,
            }
        output_validation = _validate_display_output_dir(out_dir_p, self.router_home)
        if not output_validation.get("valid"):
            return {
                "schema": "ariadne.cadctl.display_membership.v1",
                "status": "BLOCKED",
                "reason": "output directory containment changed before execution: "
                + str(output_validation.get("reason")),
                "executed": False,
                "execution_context": "dedicated_full_autocad",
                "operation": "e2.inspect.xclip_membership",
                "out_dir": str(out_dir_p),
                "geometry_scope": geometry_scope,
                "output_validation": output_validation,
            }
        try:
            existing_children = sorted(
                out_dir_p.iterdir(), key=lambda child: child.name.casefold()
            )
        except OSError as exc:
            return {
                "schema": "ariadne.cadctl.display_membership.v1",
                "status": "BLOCKED",
                "reason": "cannot inspect display-membership output directory freshness: "
                f"{type(exc).__name__}: {exc}",
                "executed": False,
                "execution_context": "dedicated_full_autocad",
                "operation": "e2.inspect.xclip_membership",
                "out_dir": str(out_dir_p),
                "geometry_scope": geometry_scope,
                "output_validation": output_validation,
            }
        if existing_children:
            return {
                "schema": "ariadne.cadctl.display_membership.v1",
                "status": "BLOCKED",
                "reason": "display-membership output directory is not fresh; pre-existing children: "
                + ", ".join(str(child) for child in existing_children),
                "executed": False,
                "execution_context": "dedicated_full_autocad",
                "operation": "e2.inspect.xclip_membership",
                "out_dir": str(out_dir_p),
                "geometry_scope": geometry_scope,
                "output_validation": output_validation,
                "out_dir_existed": out_dir_existed,
                "evidence_preserved": True,
            }
        receipt_path = out_dir_p / "display_membership_receipt.json"

        prior_evidence = [
            path
            for path in (
                receipt_path,
                out_dir_p / "display_membership_binding.json",
                out_dir_p / "target_population_oracle.json",
            )
            if os.path.lexists(path)
        ]
        if prior_evidence:
            return {
                "schema": "ariadne.cadctl.display_membership.v1",
                "status": "BLOCKED",
                "reason": "refusing to overwrite existing evidence: "
                + ", ".join(str(path) for path in prior_evidence),
                "executed": False,
                "execution_context": "dedicated_full_autocad",
                "operation": "e2.inspect.xclip_membership",
                "out_dir": str(out_dir_p),
                "geometry_scope": geometry_scope,
                "evidence_preserved": True,
            }

        pass_prepublish_guard = None

        def write_evidence(path: Path, payload: dict, *, before_publish=None) -> None:
            current_output_validation = _validate_display_output_dir(
                out_dir_p, self.router_home
            )
            if not current_output_validation.get("valid"):
                raise OSError(
                    "output containment changed: "
                    + str(current_output_validation.get("reason"))
                )
            if not _same_resolved_path(str(path.parent), out_dir_p):
                raise OSError(f"evidence path escapes output directory: {path}")
            _atomic_write_json_no_overwrite(
                path, payload, before_publish=before_publish
            )

        def finish(status: str, reason: str, *, executed: bool, **extra: object) -> dict:
            payload = {
                "schema": "ariadne.cadctl.display_membership.v1",
                "status": status,
                "reason": reason,
                "executed": executed,
                "execution_context": "dedicated_full_autocad",
                "operation": "e2.inspect.xclip_membership",
                "out_dir": str(out_dir_p),
                "geometry_scope": geometry_scope,
                **extra,
            }
            try:
                write_evidence(
                    receipt_path,
                    payload,
                    before_publish=(pass_prepublish_guard if status == "PASS" else None),
                )
            except Exception as exc:
                return {
                    **payload,
                    "status": "BLOCKED",
                    "reason": "failed to atomically publish display-membership receipt: "
                    f"{type(exc).__name__}: {exc}",
                    "evidence_write_failed": True,
                }
            payload["receipt"] = str(receipt_path)
            return payload

        if (
            not isinstance(geometry_scope, str)
            or geometry_scope not in DISPLAY_MEMBERSHIP_GEOMETRY_SCOPES
        ):
            return finish(
                "BLOCKED",
                "geometry_scope must be strict_layer_entities_v1 or linear_segments_v1",
                executed=False,
            )
        if not isinstance(target_layers, list):
            return finish("BLOCKED", "target_layers must be a non-empty list", executed=False)
        normalized_layers = []
        for value in target_layers:
            if not isinstance(value, str) or not value.strip():
                return finish(
                    "BLOCKED",
                    "every target layer must be a non-empty string",
                    executed=False,
                )
            normalized_layers.append(value)
        if not normalized_layers or len(set(normalized_layers)) != len(normalized_layers):
            return finish(
                "BLOCKED",
                "target_layers must be non-empty and unique",
                executed=False,
            )

        source = Path(dwg_path)
        if not source.is_file() or source.suffix.lower() != ".dwg":
            return finish(
                "BLOCKED",
                f"input DWG not found or not a .dwg file: {dwg_path}",
                executed=False,
            )
        source_path_error = _path_reparse_error(source)
        if source_path_error:
            return finish(
                "BLOCKED",
                "input DWG path is not a stable plain-file path: " + source_path_error,
                executed=False,
            )
        source_identity = source.resolve(strict=True)
        original_before = _sha256_head(source, 64).lower()

        native_bin = (
            self.router_home
            / "src"
            / "Ariadne.AcadNative"
            / "bin"
            / "x64"
            / "Release"
        )
        manifest_before = _verify_native_build_manifest(self.router_home, native_bin)
        manifest_common = {
            "build_manifest_path": manifest_before["path"],
            "build_manifest_sha256": manifest_before["sha256"],
            "build_manifest_validation": {"before": manifest_before},
        }
        if not manifest_before["valid"]:
            return finish(
                "NEEDS_BUILD",
                "current-checkout native build manifest cannot bind the attended artifacts: "
                + "; ".join(manifest_before["errors"]),
                executed=False,
                original_sha256_before=original_before,
                native_bin_dir=str(native_bin),
                **manifest_common,
            )
        required_native = [Path(path) for path in manifest_before["artifact_paths"]]

        try:
            stage_dir = _ensure_display_output_subdir(
                out_dir_p, "staged", self.router_home
            )
        except OSError as exc:
            return finish(
                "BLOCKED",
                f"cannot prepare safe staged output directory: {type(exc).__name__}: {exc}",
                executed=False,
                original_sha256_before=original_before,
                **manifest_common,
            )
        staged = stage_dir / "input.dwg"
        if os.path.lexists(staged):
            return finish(
                "BLOCKED",
                f"refusing to overwrite existing staged DWG: {staged}",
                executed=False,
                original_sha256_before=original_before,
                **manifest_common,
            )
        try:
            shutil.copy2(source, staged)
        except OSError as exc:
            return finish(
                "BLOCKED",
                f"could not stage original DWG: {type(exc).__name__}: {exc}",
                executed=False,
                original_sha256_before=original_before,
                staged_dwg=str(staged),
                **manifest_common,
            )
        try:
            os.chmod(staged, 0o444)
        except OSError as exc:
            return finish(
                "BLOCKED",
                f"could not make observation-only staged DWG read-only: {type(exc).__name__}: {exc}",
                executed=False,
                original_sha256_before=original_before,
                staged_dwg=str(staged),
                **manifest_common,
            )
        staged_before = _sha256_head(staged, 64).lower()
        staged_read_only_after_copy = _read_only_file_state(staged)
        if staged_before != original_before:
            return finish(
                "BLOCKED",
                "staged copy hash differs from the source before execution",
                executed=False,
                original_sha256_before=original_before,
                staged_sha256_before=staged_before,
                staged_dwg=str(staged),
                **manifest_common,
            )
        if not staged_read_only_after_copy["read_only"]:
            return finish(
                "BLOCKED",
                "observation-only staged DWG is writable after staging",
                executed=False,
                original_sha256_before=original_before,
                staged_sha256_before=staged_before,
                staged_dwg=str(staged),
                staged_read_only_evidence={
                    "required": True,
                    "after_copy": staged_read_only_after_copy,
                },
                **manifest_common,
            )

        try:
            attended_dir = _ensure_display_output_subdir(
                out_dir_p, "attended", self.router_home
            )
        except OSError as exc:
            return finish(
                "BLOCKED",
                f"cannot prepare safe attended output directory: {type(exc).__name__}: {exc}",
                executed=False,
                original_sha256_before=original_before,
                staged_sha256_before=staged_before,
                staged_dwg=str(staged),
                **manifest_common,
            )
        prelaunch_layout = _validate_display_prelaunch_layout(
            out_dir_p, stage_dir, attended_dir, self.router_home
        )
        if not prelaunch_layout["valid"]:
            return finish(
                "BLOCKED",
                "display-membership output directory is not fresh before native launch: "
                + str(prelaunch_layout["reason"]),
                executed=False,
                original_sha256_before=original_before,
                staged_sha256_before=staged_before,
                staged_dwg=str(staged),
                output_freshness=prelaunch_layout,
                **manifest_common,
            )
        staged_sha256_before_launch = _sha256_file(staged)
        staged_read_only_before_launch = _read_only_file_state(staged)
        if (
            staged_sha256_before_launch != original_before
            or not staged_read_only_before_launch["read_only"]
        ):
            return finish(
                "BLOCKED",
                "observation-only staged DWG changed or became writable before native launch",
                executed=False,
                original_sha256_before=original_before,
                staged_sha256_before=staged_before,
                staged_sha256_before_launch=staged_sha256_before_launch,
                staged_dwg=str(staged),
                staged_read_only_evidence={
                    "required": True,
                    "after_copy": staged_read_only_after_copy,
                    "before_launch": staged_read_only_before_launch,
                },
                **manifest_common,
            )
        try:
            attended = attended_lane.run_attended_native_job(
                str(staged),
                str(attended_dir),
                "e2.inspect.xclip_membership",
                {
                    "target_layers": normalized_layers,
                    "geometry_scope": geometry_scope,
                },
                timeout=timeout,
                router_home=str(self.router_home),
                native_bin_dir=str(native_bin),
            )
        except Exception as exc:
            original_after = _sha256_head(source, 64).lower()
            return finish(
                "BLOCKED",
                f"attended AutoCAD runner failed: {type(exc).__name__}: {exc}",
                executed=False,
                original_sha256_before=original_before,
                original_sha256_after=original_after,
                original_unchanged=original_before == original_after,
                staged_dwg=str(staged),
                staged_read_only_evidence={
                    "required": True,
                    "after_copy": staged_read_only_after_copy,
                    "before_launch": staged_read_only_before_launch,
                },
                **manifest_common,
            )

        original_after = _sha256_head(source, 64).lower()
        staged_read_only_after_execution = _read_only_file_state(staged)
        try:
            staged_sha256_after_execution = _sha256_file(staged)
        except OSError:
            staged_sha256_after_execution = None
        if not isinstance(attended, dict):
            return finish(
                "BLOCKED",
                "attended AutoCAD runner returned no structured execution result",
                executed=False,
                original_sha256_before=original_before,
                original_sha256_after=original_after,
                original_unchanged=original_before == original_after,
                staged_dwg=str(staged),
                **manifest_common,
            )
        execution_state = _attended_execution_state(attended)
        raw_job_out = attended_dir / "job_out.json"
        common = {
            "original_sha256_before": original_before,
            "original_sha256_after": original_after,
            "original_unchanged": original_before == original_after,
            "staged_dwg": str(staged),
            "staged_sha256_before": staged_before,
            "staged_sha256_before_launch": staged_sha256_before_launch,
            "staged_sha256_after_execution": staged_sha256_after_execution,
            "staged_read_only_evidence": {
                "required": True,
                "after_copy": staged_read_only_after_copy,
                "before_launch": staged_read_only_before_launch,
                "after_execution": staged_read_only_after_execution,
            },
            "native_bin_dir": str(native_bin),
            "attended_result_ref": str(raw_job_out),
            "attended_reported_result_ref": attended.get("result_json"),
            "attended_completion_receipt": attended.get("completion_receipt"),
            "stdout": attended.get("stdout_path"),
            "stderr": attended.get("stderr_path"),
            "degraded": bool(attended.get("degraded", False)),
            "attended_command_constructed": execution_state["command_constructed"],
            "attended_launch_observed": execution_state["launch_observed"],
            "attended_launch_evidence": execution_state["launch_evidence"],
            **manifest_common,
        }
        runtime_layout = _validate_display_runtime_layout(
            out_dir_p, stage_dir, attended_dir, staged, self.router_home
        )
        common["output_runtime_validation"] = runtime_layout
        if not runtime_layout.get("valid"):
            return finish(
                "BLOCKED",
                "display-membership path identity changed during native execution: "
                + str(runtime_layout.get("reason")),
                executed=execution_state["launch_observed"],
                **common,
            )
        if original_before != original_after:
            return finish(
                "BLOCKED",
                "SAFETY VIOLATION: original DWG changed during attended inspection",
                executed=execution_state["launch_observed"],
                **common,
            )
        if (
            staged_sha256_after_execution != staged_before
            or not staged_read_only_after_execution["read_only"]
        ):
            return finish(
                "BLOCKED",
                "SAFETY VIOLATION: observation-only staged DWG changed or became writable",
                executed=execution_state["launch_observed"],
                **common,
            )
        if attended.get("error") or attended.get("timed_out"):
            return finish(
                "BLOCKED",
                str(attended.get("error") or "attended AutoCAD run timed out"),
                executed=execution_state["launch_observed"],
                **common,
            )

        manifest_after = _verify_native_build_manifest(self.router_home, native_bin)
        common["build_manifest_validation"] = {
            "before": manifest_before,
            "after": manifest_after,
        }
        if (
            not manifest_after["valid"]
            or manifest_after["sha256"] != manifest_before["sha256"]
        ):
            return finish(
                "BLOCKED",
                "native build manifest drifted after attended execution: "
                + "; ".join(manifest_after["errors"] or ["manifest SHA changed"]),
                executed=execution_state["launch_observed"],
                **common,
            )

        if not raw_job_out.is_file() or _is_reparse_point(raw_job_out):
            return finish(
                "BLOCKED",
                "native job_out.json evidence is missing or unsafe",
                executed=execution_state["launch_observed"],
                **common,
            )
        try:
            raw_job_out_bytes = raw_job_out.read_bytes()
            native_job = _strict_json_loads(raw_job_out_bytes.decode("utf-8-sig"))
        except (OSError, UnicodeError, ValueError) as exc:
            return finish(
                "BLOCKED",
                f"native job_out.json evidence is not parseable: {type(exc).__name__}: {exc}",
                executed=execution_state["launch_observed"],
                **common,
            )
        if not isinstance(native_job, dict):
            return finish(
                "BLOCKED",
                "native job_out.json evidence is not an object",
                executed=execution_state["launch_observed"],
                **common,
            )
        attended_result = attended.get("result")
        if attended_result is not None:
            try:
                result_matches_raw = (
                    _canonical_json_bytes(attended_result)
                    == _canonical_json_bytes(native_job)
                )
            except (TypeError, ValueError) as exc:
                return finish(
                    "BLOCKED",
                    f"attended in-memory result cannot be bound to raw job_out.json: {type(exc).__name__}: {exc}",
                    executed=execution_state["launch_observed"],
                    **common,
                )
            if not result_matches_raw:
                return finish(
                    "BLOCKED",
                    "attended in-memory result does not match raw job_out.json evidence",
                    executed=execution_state["launch_observed"],
                    **common,
                )
        raw_job_out_sha256 = hashlib.sha256(raw_job_out_bytes).hexdigest()

        # job_out.json is native-operation evidence only.  It cannot show that
        # the disposable AutoCAD process was closed, the user's sessions were
        # untouched, or SECURELOAD/TRUSTEDPATHS were restored.  Do not let a
        # pre-cleanup receipt or a Python fallback promote it to PASS.
        launcher_receipt = attended.get("envelope")
        launcher_receipt_path = attended_dir / "attended_job_final_receipt.json"
        launcher_receipt_sha256 = None
        launcher_receipt_bytes = None
        receipt_errors = []
        if not isinstance(launcher_receipt, dict):
            receipt_errors.append("missing final receipt")
        else:
            reported_receipt_path = attended.get("result_json")
            if not _same_resolved_path(reported_receipt_path, launcher_receipt_path):
                receipt_errors.append("result_json")
            elif (
                not launcher_receipt_path.is_file()
                or _path_reparse_error(launcher_receipt_path) is not None
            ):
                receipt_errors.append("final_receipt_file")
            else:
                try:
                    persisted_launcher_receipt = _load_json_bom(launcher_receipt_path)
                    if _canonical_json_bytes(persisted_launcher_receipt) != _canonical_json_bytes(
                        launcher_receipt
                    ):
                        receipt_errors.append("final_receipt_bytes")
                    else:
                        launcher_receipt_sha256 = _sha256_file(launcher_receipt_path)
                        launcher_receipt_bytes = launcher_receipt_path.stat().st_size
                except (OSError, TypeError, UnicodeError, ValueError):
                    receipt_errors.append("final_receipt_file")
            if launcher_receipt.get("schema") != "ariadne.cad_os.attended_job_result.v1":
                receipt_errors.append("schema")
            if launcher_receipt.get("phase") != "finalized":
                receipt_errors.append("phase")
            if launcher_receipt.get("status") != "ok":
                receipt_errors.append("status")
            if launcher_receipt.get("operation") != "e2.inspect.xclip_membership":
                receipt_errors.append("operation")
            if launcher_receipt.get("read_only_operation") is not True:
                receipt_errors.append("read_only_operation")
            if launcher_receipt.get("staged_save_attempted") is not False:
                receipt_errors.append("staged_save_attempted")
            if not _is_positive_plain_int(launcher_receipt.get("launched_pid")):
                receipt_errors.append("launched_pid")
            launched_process_name = launcher_receipt.get("launched_process_name")
            if (
                not isinstance(launched_process_name, str)
                or launched_process_name.casefold() not in {"acad", "acad.exe"}
            ):
                receipt_errors.append("launched_process_name")
            if (
                not isinstance(launcher_receipt.get("launched_start_time_utc"), str)
                or not launcher_receipt["launched_start_time_utc"].strip()
            ):
                receipt_errors.append("launched_start_time_utc")
            if launcher_receipt.get("dedicated_instance") is not True:
                receipt_errors.append("dedicated_instance")
            if launcher_receipt.get("timed_out") is not False:
                receipt_errors.append("timed_out")
            if launcher_receipt.get("launched_pid_closed") is not True:
                receipt_errors.append("launched_pid_closed")
            if launcher_receipt.get("launched_pid_identity_verified") is not True:
                receipt_errors.append("launched_pid_identity_verified")
            if not isinstance(launcher_receipt.get("launched_pid_reused"), bool):
                receipt_errors.append("launched_pid_reused")
            if launcher_receipt.get("pre_existing_identity_verified") is not True:
                receipt_errors.append("pre_existing_identity_verified")
            pre_existing_pids = launcher_receipt.get("pre_existing_pids")
            pre_existing_processes = launcher_receipt.get("pre_existing_processes")
            pre_existing_still_alive = launcher_receipt.get("pre_existing_still_alive")
            if (
                not isinstance(pre_existing_pids, list)
                or any(
                    not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0
                    for pid in pre_existing_pids
                )
                or len(pre_existing_pids) != len(set(pre_existing_pids))
            ):
                receipt_errors.append("pre_existing_pids")
            process_pids = (
                [
                    process.get("pid")
                    for process in pre_existing_processes
                    if isinstance(process, dict)
                ]
                if isinstance(pre_existing_processes, list)
                else []
            )
            if (
                not isinstance(pre_existing_processes, list)
                or len(pre_existing_processes) != len(pre_existing_pids or [])
                or len(process_pids) != len(set(process_pids))
                or set(process_pids) != set(pre_existing_pids or [])
                or any(
                    not isinstance(process, dict)
                    or not isinstance(process.get("process_name"), str)
                    or process["process_name"].casefold() not in {"acad", "acad.exe"}
                    or not isinstance(process.get("start_time_utc"), str)
                    or not process["start_time_utc"].strip()
                    for process in pre_existing_processes
                )
            ):
                receipt_errors.append("pre_existing_processes")
            if pre_existing_still_alive != pre_existing_pids:
                receipt_errors.append("pre_existing_still_alive")
            if launcher_receipt.get("user_session_touched") is not False:
                receipt_errors.append("user_session_touched")
            if launcher_receipt.get("job_out_present") is not True:
                receipt_errors.append("job_out_present")
            if not _same_resolved_path(launcher_receipt.get("job_out"), raw_job_out):
                receipt_errors.append("job_out")
            if launcher_receipt.get("degraded") is not False or attended.get("degraded", False) is not False:
                receipt_errors.append("degraded")
            if not isinstance(launcher_receipt.get("security"), dict) or launcher_receipt["security"].get("restored") is not True:
                receipt_errors.append("security.restored")
            authority = launcher_receipt.get("receipt_authority")
            if authority == "powershell_launcher":
                if launcher_receipt.get("recovered_from_launcher_finalization_hang") is not False:
                    receipt_errors.append("recovered_from_launcher_finalization_hang")
            elif authority == "python_independent_safety_validator":
                if launcher_receipt.get("recovered_from_launcher_finalization_hang") is not True:
                    receipt_errors.append("recovered_from_launcher_finalization_hang")
                if launcher_receipt.get("powershell_helper_closed") is not True:
                    receipt_errors.append("powershell_helper_closed")
            else:
                receipt_errors.append("receipt_authority")
        if receipt_errors:
            return finish(
                "BLOCKED",
                "attended launcher final safety receipt is incomplete: " + ", ".join(receipt_errors),
                executed=execution_state["launch_observed"],
                **common,
            )
        common["attended_final_receipt_evidence"] = {
            "path": str(launcher_receipt_path.resolve()),
            "sha256": launcher_receipt_sha256,
            "bytes": launcher_receipt_bytes,
        }
        native = native_job.get("result")
        document_access = native_job.get("document_access")
        valid_outer = (
            native_job.get("schema") == "ariadne.autocad_native_job_result.v1"
            and native_job.get("engine") == "native_objectarx"
            and native_job.get("operation") == "e2.inspect.xclip_membership"
            and native_job.get("status") == "ok"
        )
        valid_inner = (
            isinstance(native, dict)
            and native.get("schema") == "ariadne.e2.native_xclip_membership_raw.v1"
            and native.get("oracle_method") == "xclip_polygon_segment_intersection"
            and native.get("host_mode") == "full_autocad"
            and native.get("native_membership_resolved") is True
        )
        if not valid_outer or not valid_inner:
            return finish(
                "BLOCKED",
                "native result is incomplete or was not produced in full_autocad",
                executed=execution_state["launch_observed"],
                **common,
            )
        valid_document_access = (
            isinstance(document_access, dict)
            and document_access.get("mode") == "read_only"
            and document_access.get("required") is True
            and document_access.get("application_context") is True
            and type(document_access.get("open_errorstatus")) is int
            and document_access.get("open_errorstatus") == 0
            and type(document_access.get("read_lock_errorstatus")) is int
            and document_access.get("read_lock_errorstatus") == 0
            and type(document_access.get("read_unlock_errorstatus")) is int
            and document_access.get("read_unlock_errorstatus") == 0
            and type(document_access.get("restore_errorstatus")) is int
            and document_access.get("restore_errorstatus") == 0
            and type(document_access.get("close_errorstatus")) is int
            and document_access.get("close_errorstatus") == 0
            and document_access.get("path_verified_before") is True
            and document_access.get("path_verified_after") is True
            and document_access.get("read_only_verified_before") is True
            and document_access.get("read_only_verified_after") is True
            and document_access.get("working_database_matches_before") is True
            and document_access.get("working_database_matches_after") is True
            and document_access.get("operation_executed") is True
            and _same_resolved_path(document_access.get("opened_path"), staged)
        )
        if not valid_document_access:
            return finish(
                "BLOCKED",
                "native result does not prove a complete read-only document lifecycle",
                executed=execution_state["launch_observed"],
                **common,
            )
        common["native_document_access"] = document_access
        if not _same_resolved_path(native.get("drawing_path"), staged):
            return finish(
                "BLOCKED",
                "native drawing_path is not the exact staged DWG requested for inspection",
                executed=execution_state["launch_observed"],
                **common,
            )
        if native.get("geometry_scope") != geometry_scope:
            return finish(
                "BLOCKED",
                "native geometry_scope does not match the requested geometry_scope",
                executed=execution_state["launch_observed"],
                **common,
            )

        raw_layers = native.get("target_layers")
        summaries = native.get("layer_summary")
        records = native.get("records")
        if (
            raw_layers != normalized_layers
            or not isinstance(summaries, list)
            or not isinstance(records, list)
        ):
            return finish(
                "BLOCKED",
                "native result target layers, summaries, or records are incomplete",
                executed=execution_state["launch_observed"],
                **common,
            )

        ids_by_layer: dict[str, list[str]] = {layer: [] for layer in normalized_layers}
        seen_ids: set[str] = set()
        try:
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError("a visible record is not an object")
                layer = record.get("source_layer")
                source_def = record.get("source_def_handle")
                entity_handle = record.get("source_entity_handle")
                lineage = record.get("lineage_path")
                subentity = record.get("subentity_ordinal")
                fragment = record.get("clip_fragment_ordinal")
                active_clips = record.get("active_xclip_handles")
                p0_world = record.get("p0_world")
                p1_world = record.get("p1_world")
                if (
                    layer not in ids_by_layer
                    or not _is_nonempty_string(source_def)
                    or not _is_nonempty_string(entity_handle)
                    or not isinstance(lineage, list)
                    or not _is_nonnegative_plain_int(subentity)
                    or not _is_nonnegative_plain_int(fragment)
                    or not isinstance(active_clips, list)
                    or any(not _is_nonempty_string(handle) for handle in active_clips)
                    or len(active_clips) != len(set(active_clips))
                    or not _is_finite_point2(p0_world)
                    or not _is_finite_point2(p1_world)
                ):
                    raise ValueError("a visible record lacks stable native lineage")

                root_handle = source_def
                if lineage:
                    first = lineage[0]
                    if not isinstance(first, dict):
                        raise ValueError("a lineage step is not an object")
                    root_handle = first.get("source_def_handle")
                    if not _is_nonempty_string(root_handle):
                        raise ValueError("a lineage root handle is not a string")
                path_uid = _hash_parts("MODELSPACE_ROOT", root_handle)
                expected_owner = root_handle
                for step in lineage:
                    if not isinstance(step, dict):
                        raise ValueError("a lineage step is not an object")
                    owner = step.get("source_def_handle")
                    insert_handle = step.get("insert_entity_handle")
                    target_def = step.get("target_def_handle")
                    row = step.get("array_row_index")
                    column = step.get("array_col_index")
                    if (
                        owner != expected_owner
                        or not _is_nonempty_string(owner)
                        or not _is_nonempty_string(insert_handle)
                        or not _is_nonempty_string(target_def)
                        or not _is_nonnegative_plain_int(row)
                        or not _is_nonnegative_plain_int(column)
                        or row != 0
                        or column != 0
                    ):
                        raise ValueError("native lineage is discontinuous or uses an unsupported array")
                    path_uid = _hash_parts(path_uid, insert_handle, target_def, row, column)
                    expected_owner = target_def
                if expected_owner != source_def:
                    raise ValueError("native lineage does not terminate at source_def_handle")
                placed_uid = _hash_parts(path_uid, entity_handle, subentity, fragment)
                if placed_uid in seen_ids:
                    raise ValueError("duplicate stable visible segment identity")
                seen_ids.add(placed_uid)
                ids_by_layer[str(layer)].append(placed_uid)
        except (TypeError, ValueError) as exc:
            return finish(
                "BLOCKED",
                f"native visible lineage is invalid: {exc}",
                executed=execution_state["launch_observed"],
                **common,
            )

        summaries_by_layer = {}
        for row in summaries:
            layer = row.get("layer") if isinstance(row, dict) else None
            if layer not in ids_by_layer or layer in summaries_by_layer:
                return finish(
                    "BLOCKED",
                    "native layer_summary is ambiguous, duplicated, or names another layer",
                    executed=execution_state["launch_observed"],
                    **common,
                )
            summaries_by_layer[layer] = row
        if len(summaries_by_layer) != len(normalized_layers):
            return finish(
                "BLOCKED",
                "native layer_summary does not contain exactly one row per target layer",
                executed=execution_state["launch_observed"],
                **common,
            )
        targets = []
        for index, layer in enumerate(normalized_layers, start=1):
            row = summaries_by_layer.get(layer)
            visible_ids = sorted(ids_by_layer[layer])
            if not isinstance(row, dict):
                return finish(
                    "BLOCKED",
                    f"native result has no summary for target layer {layer!r}",
                    executed=execution_state["launch_observed"],
                    **common,
                )
            visible_count = row.get("native_visible_source_segments")
            expected_count = row.get("expected_source_segments")
            clipped_count = row.get("clipped_away_source_segments")
            template_count = row.get("native_source_entity_templates")
            excluded_curved_count = row.get("excluded_curved_source_segments")
            excluded_degenerate_count = row.get(
                "excluded_degenerate_source_segments"
            )
            excluded_unsupported_template_count = row.get(
                "excluded_unsupported_entity_templates"
            )
            if (
                not _is_nonnegative_plain_int(visible_count)
                or not _is_nonnegative_plain_int(expected_count)
                or not _is_nonnegative_plain_int(clipped_count)
                or not _is_nonnegative_plain_int(template_count)
                or not _is_nonnegative_plain_int(excluded_curved_count)
                or not _is_nonnegative_plain_int(excluded_degenerate_count)
                or not _is_nonnegative_plain_int(excluded_unsupported_template_count)
                or min(
                    visible_count,
                    expected_count,
                    clipped_count,
                    template_count,
                    excluded_curved_count,
                    excluded_degenerate_count,
                    excluded_unsupported_template_count,
                ) < 0
                or expected_count != visible_count + clipped_count
                or visible_count != len(visible_ids)
                or (
                    geometry_scope == DISPLAY_MEMBERSHIP_STRICT_LAYER_ENTITIES_V1
                    and (
                        excluded_curved_count != 0
                        or excluded_degenerate_count != 0
                        or excluded_unsupported_template_count != 0
                    )
                )
            ):
                return finish(
                    "BLOCKED",
                    f"native conservation or visible identity count failed for {layer!r}",
                    executed=execution_state["launch_observed"],
                    **common,
                )
            targets.append(
                {
                    "target_id": f"target-{index:03d}",
                    "layer": layer,
                    "native_source_entity_templates": template_count,
                    "expected_source_segments": expected_count,
                    "native_visible_source_segments": visible_count,
                    "clipped_away_source_segments": clipped_count,
                    "excluded_curved_source_segments": excluded_curved_count,
                    "excluded_degenerate_source_segments": excluded_degenerate_count,
                    "excluded_unsupported_entity_templates": excluded_unsupported_template_count,
                    "native_visible_segment_ids": visible_ids,
                }
            )

        raw_evidence = raw_job_out
        if _sha256_file(raw_evidence) != raw_job_out_sha256:
            return finish(
                "BLOCKED",
                "native job_out.json changed after raw evidence was parsed",
                executed=execution_state["launch_observed"],
                **common,
            )
        manifest_before_evidence = _verify_native_build_manifest(
            self.router_home, native_bin
        )
        common["build_manifest_validation"]["before_evidence"] = manifest_before_evidence
        if (
            not manifest_before_evidence["valid"]
            or manifest_before_evidence["sha256"] != manifest_before["sha256"]
        ):
            return finish(
                "BLOCKED",
                "native build manifest drifted before evidence publication: "
                + "; ".join(
                    manifest_before_evidence["errors"] or ["manifest SHA changed"]
                ),
                executed=execution_state["launch_observed"],
                **common,
            )
        binding_path = out_dir_p / "display_membership_binding.json"
        binding = {
            "schema": "ariadne.e2.native_display_binding.v1",
            "source_path": str(source.resolve()),
            "source_sha256": original_before,
            "staged_path": str(staged.resolve()),
            "staged_sha256_before": staged_before,
            "staged_read_only_evidence": common["staged_read_only_evidence"],
            "native_document_access": common["native_document_access"],
            "geometry_scope": geometry_scope,
            "native_job_out_path": str(raw_evidence.resolve()),
            "native_job_out_sha256": raw_job_out_sha256,
            "attended_final_receipt": {
                "path": str(launcher_receipt_path.resolve()),
                "sha256": launcher_receipt_sha256,
                "bytes": launcher_receipt_bytes,
            },
            "native_artifacts": [
                {
                    "leaf": path.name,
                    "path": str(path.resolve()),
                    "sha256": _sha256_file(path),
                    "bytes": path.stat().st_size,
                }
                for path in required_native
            ],
            "native_build_manifest": {
                "path": str(Path(manifest_before["path"]).resolve()),
                "sha256": manifest_before["sha256"],
                "validation": {
                    "before": {
                        "valid": manifest_before["valid"],
                        "checks": manifest_before["checks"],
                    },
                    "after_execution": {
                        "valid": manifest_after["valid"],
                        "checks": manifest_after["checks"],
                    },
                    "before_evidence": {
                        "valid": manifest_before_evidence["valid"],
                        "checks": manifest_before_evidence["checks"],
                    },
                },
            },
            "execution_context": "dedicated_full_autocad",
            "headless_fallback": False,
        }
        try:
            write_evidence(binding_path, binding)
        except Exception as exc:
            return finish(
                "BLOCKED",
                f"failed to atomically publish binding evidence: {type(exc).__name__}: {exc}",
                executed=execution_state["launch_observed"],
                **common,
            )
        try:
            written_binding = _load_json_bom(binding_path)
            raw_binding_valid = (
                isinstance(written_binding, dict)
                and written_binding.get("native_job_out_sha256") == raw_job_out_sha256
                and _sha256_file(raw_evidence) == raw_job_out_sha256
            )
        except (OSError, UnicodeError, ValueError) as exc:
            return finish(
                "BLOCKED",
                f"published binding evidence cannot be verified: {type(exc).__name__}: {exc}",
                executed=execution_state["launch_observed"],
                **common,
            )
        if not raw_binding_valid:
            return finish(
                "BLOCKED",
                "raw job_out.json SHA does not match published binding evidence",
                executed=execution_state["launch_observed"],
                **common,
            )
        binding_sha256 = _sha256_file(binding_path)
        oracle_path = out_dir_p / "target_population_oracle.json"
        oracle = {
            "schema": "ariadne.e2.target_population_oracle.v1",
            "oracle": "autocad.native_display_membership.v1",
            "status": "OBSERVED",
            "claim_scope": "instrument_observation_only",
            "producer_receipt_required": True,
            "producer_receipt_path": str(receipt_path.resolve()),
            "downstream_experiment_guard_required": True,
            "drawing_id": original_before,
            "geometry_scope": geometry_scope,
            "evidence": [
                {"path": str(raw_evidence.resolve()), "sha256": raw_job_out_sha256},
                {
                    "path": str(launcher_receipt_path.resolve()),
                    "sha256": launcher_receipt_sha256,
                },
                {
                    "path": str(binding_path.resolve()),
                    "sha256": binding_sha256,
                },
                {
                    "path": str(Path(manifest_before["path"]).resolve()),
                    "sha256": manifest_before["sha256"],
                },
            ],
            "targets": targets,
        }
        manifest_final = _verify_native_build_manifest(self.router_home, native_bin)
        common["build_manifest_validation"]["final"] = manifest_final
        if (
            not manifest_final["valid"]
            or manifest_final["sha256"] != manifest_before["sha256"]
            or _sha256_file(raw_evidence) != raw_job_out_sha256
        ):
            return finish(
                "BLOCKED",
                "native build or raw evidence drifted before oracle publication: "
                + "; ".join(manifest_final["errors"] or ["manifest or raw SHA changed"]),
                executed=execution_state["launch_observed"],
                **common,
            )
        try:
            write_evidence(oracle_path, oracle)
        except Exception as exc:
            return finish(
                "BLOCKED",
                f"failed to atomically publish target oracle: {type(exc).__name__}: {exc}",
                executed=execution_state["launch_observed"],
                **common,
            )
        oracle_sha256 = _sha256_file(oracle_path)

        @contextmanager
        def verify_final_pass_inputs():
            native_source_paths = [
                self.router_home / item["path"]
                for item in _native_source_inputs(self.router_home)
            ]
            stability_paths = [
                out_dir_p,
                stage_dir,
                attended_dir,
                source.parent,
                source,
                staged,
                raw_evidence,
                launcher_receipt_path,
                binding_path,
                oracle_path,
                Path(manifest_before["path"]),
                self.router_home / _NATIVE_BUILD_RECIPE_PATH,
                *required_native,
                *native_source_paths,
            ]
            with _hold_windows_paths_stable(stability_paths):
                final_layout = _validate_display_runtime_layout(
                    out_dir_p, stage_dir, attended_dir, staged, self.router_home
                )
                if not final_layout.get("valid"):
                    raise OSError(
                        "runtime path identity changed before PASS publication: "
                        + str(final_layout.get("reason"))
                    )
                immutable_inputs = (
                    ("original DWG", source, original_before),
                    ("staged DWG", staged, staged_before),
                    ("raw native job", raw_evidence, raw_job_out_sha256),
                    (
                        "attended final receipt",
                        launcher_receipt_path,
                        launcher_receipt_sha256,
                    ),
                    ("binding evidence", binding_path, binding_sha256),
                    ("observation oracle", oracle_path, oracle_sha256),
                )
                for label, evidence_path, expected_sha256 in immutable_inputs:
                    if (
                        not evidence_path.is_file()
                        or _path_reparse_error(evidence_path) is not None
                        or _sha256_file(evidence_path) != expected_sha256
                    ):
                        raise OSError(f"{label} changed before PASS publication")
                if not _same_resolved_path(
                    str(source.resolve(strict=True)), source_identity
                ):
                    raise OSError(
                        "original DWG path identity changed before PASS publication"
                    )
                if _sha256_file(source) != _sha256_file(staged):
                    raise OSError(
                        "staged DWG no longer matches the original before PASS publication"
                    )
                staged_read_only_final = _read_only_file_state(staged)
                if not staged_read_only_final["read_only"]:
                    raise OSError(
                        "staged DWG became writable before PASS publication: "
                        + str(staged_read_only_final["reason"])
                    )
                final_manifest = _verify_native_build_manifest(
                    self.router_home, native_bin
                )
                if (
                    not final_manifest["valid"]
                    or final_manifest["sha256"] != manifest_before["sha256"]
                ):
                    raise OSError(
                        "native build manifest changed before PASS publication: "
                        + "; ".join(
                            final_manifest["errors"] or ["manifest SHA changed"]
                        )
                    )
                yield

        pass_prepublish_guard = verify_final_pass_inputs
        return finish(
            "PASS",
            "full AutoCAD/ObjectARX resolved every target segment with conserved native lineage",
            executed=execution_state["launch_observed"],
            target_population_oracle=str(oracle_path),
            target_population_oracle_sha256=oracle_sha256,
            binding_evidence=str(binding_path),
            binding_evidence_sha256=binding_sha256,
            claim_scope="instrument_observation_only",
            downstream_experiment_guard_required=True,
            authoritative_completion_marker=str(receipt_path),
            final_evidence_sha256={
                "source": original_before,
                "staged_dwg": staged_before,
                "native_job_out": raw_job_out_sha256,
                "attended_final_receipt": launcher_receipt_sha256,
                "binding": binding_sha256,
                "observation_oracle": oracle_sha256,
                "native_build_manifest": manifest_before["sha256"],
            },
            native_visible_source_segments=sum(
                target["native_visible_source_segments"] for target in targets
            ),
            **common,
        )

    def live_status(self) -> dict:
        return {
            "schema": "ariadne.cadctl.live_status.v1",
            "status": "not_implemented",
            "live": False,
            "reason": "No persistent attended ObjectARX live pump is attached to cadctl. Use staged router operations; M07 owns deep live surface completion.",
        }

    # ----------------------------------------------------------------- helpers
    def _build_cad_job(self, operation: str, original: str,
                       staged_meta: dict | None, mode: str) -> dict:
        sel = route_select.operation_route(operation)
        if not sel.get("found"):
            sel = route_select.intent_route("dwg")
        job = {
            "schema": "ariadne.autocad_sdk_job.v1",
            "operation": operation,
            "write_mode": "read",
            "output_mode": "ir" if mode == "graph" else "extract",
            "issued_by": "cadctl",
            "issued_at": _now_iso(),
            "route": sel.get("route", "dwg_truth_autocad"),
            "extract_mode": "geometry_native",
            "input": {
                "original_path": str(Path(original).resolve()) if Path(original).exists() else str(original),
            },
        }
        if staged_meta:
            job["input"]["staged_copy"] = staged_meta.get("staged_copy")
            job["input"]["byte_size"] = staged_meta.get("byte_size")
            job["input"]["sha256_16"] = staged_meta.get("sha256_16")
        return job

    def _inspect_envelope(self, status_word: str, result: dict,
                          cad_job_path: Path, cad_result_path: Path,
                          stdout_path: str | None, stderr_path: str | None,
                          staged: str | None, ir_path: str | None = None,
                          entity_count=None, reason: str | None = None) -> dict:
        env = {
            "schema": "ariadne.cadctl.inspect.v1",
            "status": status_word,
            "operation": result.get("operation"),
            "registry_operation_status": (
                result.get("registry_operation_status")
                or self._registry_operation_status(result.get("operation"))
            ),
            "cad_job": str(cad_job_path),
            "cad_result": str(cad_result_path),
            "stdout": stdout_path,
            "stderr": stderr_path,
            "staged_copy": staged,
            "result_status": result.get("status"),
        }
        if ir_path:
            env["dwg_graph_ir"] = ir_path
        if entity_count is not None:
            env["entity_count"] = entity_count
        if reason:
            env["reason"] = reason
        return env


# Module-level convenience wrappers (so callers can `from cadctl import status`).
def status() -> dict:
    return Cad().status()


def inspect(dwg_path: str, out_dir: str, mode: str = "graph",
            include_rich: bool = False) -> dict:
    return Cad().inspect(dwg_path, out_dir, mode, include_rich)


def query(ir_path: str, sql: str) -> dict:
    return Cad().query(ir_path, sql)


def get_entity(ir_path: str, handle: str) -> dict:
    return Cad().get_entity(ir_path, handle)


def validate(ir_path: str) -> dict:
    return Cad().validate(ir_path)


def registry_list() -> dict:
    return Cad().registry_list()


def registry_coverage() -> dict:
    return Cad().registry_coverage()


def registry_explain(op_id: str) -> dict:
    return Cad().registry_explain(op_id)


def run_operation(op_id: str, args: dict | None = None, write_mode: str | None = None,
                  dwg_path: str | None = None, out_dir: str | None = None) -> dict:
    return Cad().run_operation(op_id, args, write_mode, dwg_path, out_dir)


def run_command_template(template_id: str, slots: dict,
                         dwg: str | None = None, *,
                         timeout_sec: float | None = None) -> dict:
    return Cad().run_command_template(template_id, slots, dwg, timeout_sec=timeout_sec)


def patch_dry_run(patch: dict) -> dict:
    return Cad().patch_dry_run(patch)


def patch_apply_staged(patch: dict, dwg_path: str, out_dir: str) -> dict:
    return Cad().patch_apply_staged(patch, dwg_path, out_dir)


def diff_before_after(pre_ir_path: str, post_ir_path: str) -> dict:
    return Cad().diff_before_after(pre_ir_path, post_ir_path)


def visual_report(source_ref: str, kind: str = "png",
                  artifact_id: str | None = None, out_dir: str | None = None,
                  route: str | None = None) -> dict:
    return Cad().visual_report(source_ref, kind, artifact_id, out_dir, route)


def inspect_display_membership(dwg_path: str, target_layers: list[str],
                               out_dir: str | None = None, *,
                               geometry_scope: str = DISPLAY_MEMBERSHIP_STRICT_LAYER_ENTITIES_V1,
                               timeout: int = 240) -> dict:
    return Cad().inspect_display_membership(
        dwg_path, target_layers, out_dir,
        geometry_scope=geometry_scope,
        timeout=timeout,
    )


def live_status() -> dict:
    return Cad().live_status()
