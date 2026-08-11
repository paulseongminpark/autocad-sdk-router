"""Alias-safe immutable byte snapshots for verification inputs.

Every file is opened first, validated from the resulting operating-system
handle, and only then read.  The Windows implementation deliberately grants
only ``FILE_SHARE_READ`` while a capture is in progress, so none of the opened
files can be replaced, deleted, or written while the multi-file generation is
being collected.
"""
from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Mapping, Sequence


class SnapshotCaptureError(OSError):
    """A requested byte generation could not be captured safely."""


@dataclass(frozen=True)
class CapturedFile:
    """One immutable regular-file generation."""

    content: bytes
    sha256: str
    byte_count: int
    final_path: str
    identity: str
    link_count: int


@dataclass(frozen=True)
class ImmutableFileSnapshot:
    """An immutable, deterministic collection of captured file generations."""

    files: Mapping[str, CapturedFile]
    aggregate_sha256: str

    def same_generation_as(self, other: object) -> bool:
        """Return whether both captures identify the same files and bytes."""

        if not isinstance(other, ImmutableFileSnapshot):
            return False
        if tuple(self.files) != tuple(other.files):
            return False
        return all(self.files[label] == other.files[label] for label in self.files)


@dataclass(frozen=True)
class FileRequest:
    root: Path
    relative_path: str
    require_single_link: bool = False


@dataclass
class FileSnapshotLease:
    """A captured generation whose read-only OS handles remain open."""

    snapshot: ImmutableFileSnapshot
    _handles: list[object]
    _closed: bool = False

    @property
    def files(self) -> Mapping[str, CapturedFile]:
        return self.snapshot.files

    @property
    def aggregate_sha256(self) -> str:
        return self.snapshot.aggregate_sha256

    def same_generation_as(self, other: object) -> bool:
        if isinstance(other, FileSnapshotLease):
            other = other.snapshot
        return self.snapshot.same_generation_as(other)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for handle in reversed(self._handles):
            if os.name == "nt":
                _CloseHandle(handle)
            else:
                os.close(handle)
        self._handles.clear()

    def __enter__(self) -> "FileSnapshotLease":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            # Destructors run during interpreter teardown as a last-resort
            # safeguard; explicit callers still receive close errors.
            pass


def _lexical_request(root: Path, relative_path: str | Path) -> tuple[str, str]:
    root_text = os.path.abspath(os.fspath(root))
    raw_relative = os.fspath(relative_path).replace("\\", "/")
    relative = PurePosixPath(raw_relative)
    if (
        not raw_relative
        or relative.is_absolute()
        or any(part in {"", ".", ".."} for part in relative.parts)
        or (relative.parts and ":" in relative.parts[0])
    ):
        raise SnapshotCaptureError(
            f"snapshot path must be a normalized root-relative path: {relative_path}"
        )
    normalized_relative = relative.as_posix()
    expected = os.path.abspath(
        os.path.join(root_text, *normalized_relative.split("/"))
    )
    try:
        within_root = os.path.commonpath((root_text, expected)) == root_text
    except ValueError:
        within_root = False
    if not within_root:
        raise SnapshotCaptureError(
            f"snapshot path escapes its lexical root: {relative_path}"
        )
    return normalized_relative, expected


def _normalized_final_path(path: str) -> str:
    if path.startswith("\\\\?\\UNC\\"):
        path = "\\\\" + path[8:]
    elif path.startswith("\\\\?\\"):
        path = path[4:]
    return os.path.normcase(os.path.normpath(path))


def _expected_final_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


if os.name == "nt":
    import ctypes
    import ctypes.wintypes as wintypes

    _GENERIC_READ = 0x80000000
    _FILE_SHARE_READ = 0x00000001
    _OPEN_EXISTING = 3
    _FILE_ATTRIBUTE_NORMAL = 0x00000080
    _FILE_TYPE_DISK = 0x0001
    _FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    _VOLUME_NAME_DOS = 0x0
    _FILE_NAME_NORMALIZED = 0x0
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _CreateFileW = _kernel32.CreateFileW
    _CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    _CreateFileW.restype = wintypes.HANDLE
    _GetFileType = _kernel32.GetFileType
    _GetFileType.argtypes = (wintypes.HANDLE,)
    _GetFileType.restype = wintypes.DWORD
    _GetFileInformationByHandle = _kernel32.GetFileInformationByHandle
    _GetFileInformationByHandle.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION),
    )
    _GetFileInformationByHandle.restype = wintypes.BOOL
    _GetFinalPathNameByHandleW = _kernel32.GetFinalPathNameByHandleW
    _GetFinalPathNameByHandleW.argtypes = (
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    _GetFinalPathNameByHandleW.restype = wintypes.DWORD
    _ReadFile = _kernel32.ReadFile
    _ReadFile.argtypes = (
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    )
    _ReadFile.restype = wintypes.BOOL
    _CloseHandle = _kernel32.CloseHandle
    _CloseHandle.argtypes = (wintypes.HANDLE,)
    _CloseHandle.restype = wintypes.BOOL


def _win_error(action: str, path: str) -> SnapshotCaptureError:
    error = ctypes.get_last_error()
    detail = ctypes.FormatError(error).strip()
    return SnapshotCaptureError(f"{action} failed for {path}: [{error}] {detail}")


def _windows_open(expected: str) -> tuple[object, str, str, int]:
    handle = _CreateFileW(
        expected,
        _GENERIC_READ,
        _FILE_SHARE_READ,
        None,
        _OPEN_EXISTING,
        _FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle == _INVALID_HANDLE_VALUE:
        raise _win_error("CreateFileW", expected)
    try:
        if _GetFileType(handle) != _FILE_TYPE_DISK:
            raise SnapshotCaptureError(
                f"snapshot input is not a regular disk file: {expected}"
            )
        information = _BY_HANDLE_FILE_INFORMATION()
        if not _GetFileInformationByHandle(handle, ctypes.byref(information)):
            raise _win_error("GetFileInformationByHandle", expected)
        if information.dwFileAttributes & _FILE_ATTRIBUTE_DIRECTORY:
            raise SnapshotCaptureError(
                f"snapshot input is not a regular file: {expected}"
            )
        size = 512
        while True:
            buffer = ctypes.create_unicode_buffer(size)
            length = _GetFinalPathNameByHandleW(
                handle,
                buffer,
                size,
                _FILE_NAME_NORMALIZED | _VOLUME_NAME_DOS,
            )
            if length == 0:
                raise _win_error("GetFinalPathNameByHandleW", expected)
            if length < size:
                final_path = buffer.value
                break
            size = length + 1
        if _normalized_final_path(final_path) != _expected_final_path(expected):
            raise SnapshotCaptureError(
                "opened handle final path does not match its lexical path; "
                f"possible alias, symlink, or reparse escape: expected={expected!r}; "
                f"final={final_path!r}"
            )
        identity = (
            f"{information.dwVolumeSerialNumber:08x}:"
            f"{information.nFileIndexHigh:08x}{information.nFileIndexLow:08x}:"
            f"{information.ftLastWriteTime.dwHighDateTime:08x}"
            f"{information.ftLastWriteTime.dwLowDateTime:08x}:"
            f"{information.nFileSizeHigh:08x}{information.nFileSizeLow:08x}"
        )
        return handle, final_path, identity, int(information.nNumberOfLinks)
    except BaseException:
        _CloseHandle(handle)
        raise


def _windows_read(handle: object, path: str) -> bytes:
    chunks: list[bytes] = []
    buffer = ctypes.create_string_buffer(1 << 20)
    while True:
        read = wintypes.DWORD()
        if not _ReadFile(
            handle,
            buffer,
            len(buffer),
            ctypes.byref(read),
            None,
        ):
            raise _win_error("ReadFile", path)
        if read.value == 0:
            return b"".join(chunks)
        chunks.append(buffer.raw[: read.value])


def _posix_final_path(fd: int, expected: str) -> str:
    proc_path = f"/proc/self/fd/{fd}"
    if os.path.exists(proc_path):
        target = os.readlink(proc_path)
        if not os.path.isabs(target):
            target = os.path.abspath(os.path.join(os.path.dirname(proc_path), target))
        return target
    dev_path = f"/dev/fd/{fd}"
    if os.path.exists(dev_path):
        return os.path.realpath(dev_path)
    raise SnapshotCaptureError(
        f"cannot determine the opened file descriptor final path: {expected}"
    )


def _posix_open(expected: str) -> tuple[int, str, str, int]:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(expected, flags)
    except OSError as exc:
        raise SnapshotCaptureError(
            f"open failed for {expected}: {type(exc).__name__}: {exc}"
        ) from exc
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise SnapshotCaptureError(
                f"snapshot input is not a regular file: {expected}"
            )
        final_path = _posix_final_path(fd, expected)
        if _normalized_final_path(final_path) != _expected_final_path(expected):
            raise SnapshotCaptureError(
                "opened descriptor final path does not match its lexical path; "
                f"possible alias, symlink, or reparse escape: expected={expected!r}; "
                f"final={final_path!r}"
            )
        identity = (
            f"{metadata.st_dev:x}:{metadata.st_ino:x}:"
            f"{metadata.st_ctime_ns:x}:{metadata.st_mtime_ns:x}:"
            f"{metadata.st_size:x}"
        )
        return fd, final_path, identity, int(metadata.st_nlink)
    except BaseException:
        os.close(fd)
        raise


def _posix_read(fd: int, path: str) -> bytes:
    before = os.fstat(fd)
    chunks: list[bytes] = []
    while True:
        try:
            chunk = os.read(fd, 1 << 20)
        except OSError as exc:
            raise SnapshotCaptureError(
                f"read failed for {path}: {type(exc).__name__}: {exc}"
            ) from exc
        if not chunk:
            after = os.fstat(fd)
            before_generation = (
                before.st_dev,
                before.st_ino,
                before.st_ctime_ns,
                before.st_mtime_ns,
                before.st_size,
            )
            after_generation = (
                after.st_dev,
                after.st_ino,
                after.st_ctime_ns,
                after.st_mtime_ns,
                after.st_size,
            )
            if before_generation != after_generation:
                raise SnapshotCaptureError(
                    f"file generation changed while its descriptor was read: {path}"
                )
            return b"".join(chunks)
        chunks.append(chunk)


def acquire_file_set(
    requests: Mapping[str, FileRequest | tuple[Path, str]],
) -> FileSnapshotLease:
    """Capture files and retain read-only handles until ``close`` is called."""

    prepared: list[tuple[str, str, bool]] = []
    for label in sorted(requests):
        request = requests[label]
        if isinstance(request, FileRequest):
            root = request.root
            relative_path = request.relative_path
            require_single_link = request.require_single_link
        else:
            root, relative_path = request
            require_single_link = False
        _, expected = _lexical_request(Path(root), relative_path)
        prepared.append((label, expected, require_single_link))

    opened: list[tuple[str, str, object, str, str, int]] = []
    identity_labels: dict[str, str] = {}
    try:
        for label, expected, require_single_link in prepared:
            if os.name == "nt":
                handle, final_path, identity, link_count = _windows_open(expected)
            else:
                handle, final_path, identity, link_count = _posix_open(expected)
            if require_single_link and link_count != 1:
                if os.name == "nt":
                    _CloseHandle(handle)
                else:
                    os.close(handle)
                raise SnapshotCaptureError(
                    "protected snapshot input has more than one filesystem link; "
                    f"possible hardlink alias: {label!r}, link_count={link_count}"
                )
            previous_label = identity_labels.get(identity)
            if previous_label is not None:
                if os.name == "nt":
                    _CloseHandle(handle)
                else:
                    os.close(handle)
                raise SnapshotCaptureError(
                    "distinct snapshot paths resolve to one file identity; "
                    f"possible hardlink alias: {previous_label!r}, {label!r}"
                )
            identity_labels[identity] = label
            opened.append(
                (label, expected, handle, final_path, identity, link_count)
            )

        captured: dict[str, CapturedFile] = {}
        for label, expected, handle, final_path, identity, link_count in opened:
            if os.name == "nt":
                content = _windows_read(handle, expected)
            else:
                content = _posix_read(handle, expected)
            captured[label] = CapturedFile(
                content=content,
                sha256=hashlib.sha256(content).hexdigest(),
                byte_count=len(content),
                final_path=final_path,
                identity=identity,
                link_count=link_count,
            )
    except BaseException:
        for _, _, handle, _, _, _ in reversed(opened):
            if os.name == "nt":
                _CloseHandle(handle)
            else:
                os.close(handle)
        raise

    aggregate = hashlib.sha256()
    for label in sorted(captured):
        item = captured[label]
        aggregate.update(
            f"{label}\0{item.sha256}\0{item.byte_count}\n".encode("utf-8")
        )
    snapshot = ImmutableFileSnapshot(
        files=MappingProxyType(dict(sorted(captured.items()))),
        aggregate_sha256=aggregate.hexdigest(),
    )
    return FileSnapshotLease(
        snapshot=snapshot,
        _handles=[item[2] for item in opened],
    )


def capture_file_set(
    requests: Mapping[str, FileRequest | tuple[Path, str]],
) -> ImmutableFileSnapshot:
    """Open, validate, and read one immutable multi-root file generation."""

    lease = acquire_file_set(requests)
    try:
        return lease.snapshot
    finally:
        lease.close()


def capture_files(
    root: Path,
    relative_paths: Sequence[str | Path],
) -> ImmutableFileSnapshot:
    """Capture regular files beneath one lexical root."""

    requests: dict[str, FileRequest] = {}
    for relative_path in relative_paths:
        label, _ = _lexical_request(Path(root), relative_path)
        if label in requests:
            raise SnapshotCaptureError(f"duplicate snapshot path: {label}")
        requests[label] = FileRequest(Path(root), label)
    return capture_file_set(requests)
