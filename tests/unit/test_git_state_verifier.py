from __future__ import annotations

import hashlib
import inspect
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.verification import git_state
from tools.verification.git_state import (
    observe_native_source_checkout,
    verify_checkout,
    verify_paths_at_revision,
)


def test_git_runner_detaches_from_protocol_stdin_and_disables_prompts(
    tmp_path: Path,
) -> None:
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=b"ok\n", stderr=b""
    )
    with (
        patch.object(git_state, "_resolve_git_executable", return_value="git-real"),
        patch.object(git_state.subprocess, "run", return_value=completed) as run,
    ):
        assert git_state._run_git_bytes(tmp_path, ("status",)) == b"ok\n"

    args, kwargs = run.call_args
    assert args[0][0] == "git-real"
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert kwargs["env"]["GIT_NO_REPLACE_OBJECTS"] == "1"


def test_git_for_windows_cmd_shim_resolves_to_native_executable(
    tmp_path: Path,
) -> None:
    root = tmp_path / "Git"
    shim = root / "cmd" / "git.exe"
    native = root / "mingw64" / "bin" / "git.exe"
    shim.parent.mkdir(parents=True)
    native.parent.mkdir(parents=True)
    shim.write_bytes(b"shim")
    native.write_bytes(b"native")

    with (
        patch.object(git_state.shutil, "which", return_value=str(shim)),
        patch.object(git_state.os, "name", "nt"),
    ):
        assert Path(git_state._resolve_git_executable()) == native.resolve()


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _committed_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _git(repo, "config", "user.name", "Git State Test")
    _git(repo, "config", "user.email", "git-state@example.invalid")
    (repo / "tracked.txt").write_text("anchored\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "--quiet", "-m", "anchor")
    return repo, _git(repo, "rev-parse", "HEAD")


def test_verify_checkout_accepts_an_exact_clean_anchor(tmp_path: Path) -> None:
    repo, head = _committed_repo(tmp_path)

    receipt = verify_checkout(repo, head)

    assert receipt == {
        "schema": "ariadne.cad_os.checkout_verification.v1",
        "status": "PASS",
        "available": True,
        "repo_root": str(repo.resolve()),
        "expected_head": head,
        "head": head,
        "clean": True,
        "status_sha256": hashlib.sha256(b"").hexdigest(),
        "checks": {
            "expected_head_format": True,
            "git_available": True,
            "head_matches": True,
            "clean": True,
            "index_visibility_unmodified": True,
            "start_end_consistent": True,
        },
        "errors": [],
    }


def test_verify_checkout_cannot_be_redirected_by_inherited_git_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    victim_parent = tmp_path / "victim-parent"
    other_parent = tmp_path / "other-parent"
    victim_parent.mkdir()
    other_parent.mkdir()
    victim, victim_head = _committed_repo(victim_parent)
    other, _ = _committed_repo(other_parent)
    (other / "tracked.txt").write_text("other checkout\n", encoding="utf-8")
    _git(other, "add", "tracked.txt")
    _git(other, "commit", "--quiet", "-m", "other anchor")
    other_head = _git(other, "rev-parse", "HEAD")
    assert other_head != victim_head
    (victim / "untracked.txt").write_text("dirty victim\n", encoding="utf-8")

    monkeypatch.setenv("GIT_DIR", _git(other, "rev-parse", "--absolute-git-dir"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.fsmonitor")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")

    receipt = verify_checkout(victim, other_head)

    assert receipt["status"] == "BLOCKED"
    assert receipt["repo_root"] == str(victim.resolve())
    assert receipt["head"] == victim_head
    assert receipt["clean"] is False
    assert {error["code"] for error in receipt["errors"]} == {
        "HEAD_MISMATCH",
        "WORKTREE_DIRTY",
    }


def test_verify_checkout_requires_the_exact_repository_top_level(tmp_path: Path) -> None:
    repo, _ = _committed_repo(tmp_path)
    nested = repo / "nested"
    nested.mkdir()
    (nested / "owned.txt").write_text("nested\n", encoding="utf-8")
    _git(repo, "add", "nested/owned.txt")
    _git(repo, "commit", "--quiet", "-m", "nested path")
    head = _git(repo, "rev-parse", "HEAD")

    receipt = verify_checkout(nested, head)

    assert receipt["status"] == "BLOCKED"
    assert receipt["repo_root"] == str(nested.resolve())
    assert receipt["errors"] == [
        {
            "code": "GIT_ROOT_MISMATCH",
            "message": "git top-level does not match repo_root",
        }
    ]


@pytest.mark.parametrize(
    "invalid_head",
    ["a" * 39, "A" * 40, "g" * 40, "a" * 41],
)
def test_verify_checkout_rejects_any_non_exact_lowercase_sha(
    tmp_path: Path, invalid_head: str
) -> None:
    repo, _ = _committed_repo(tmp_path)

    receipt = verify_checkout(repo, invalid_head)

    assert receipt["status"] == "BLOCKED"
    assert receipt["observation"] == "NOT_ATTEMPTED"
    assert receipt["available"] == "UNKNOWN"
    assert receipt["head"] == "UNKNOWN"
    assert receipt["clean"] == "UNKNOWN"
    assert receipt["status_sha256"] == "UNKNOWN"
    assert receipt["checks"]["expected_head_format"] is False
    assert receipt["checks"]["git_available"] == "UNKNOWN"
    assert receipt["errors"] == [
        {
            "code": "EXPECTED_HEAD_INVALID",
            "message": (
                "expected_head must be exactly 40 lowercase hexadecimal characters"
            ),
        }
    ]


@pytest.mark.parametrize("dirty_kind", ["tracked", "untracked"])
def test_verify_checkout_blocks_tracked_and_untracked_dirt(
    tmp_path: Path, dirty_kind: str
) -> None:
    repo, head = _committed_repo(tmp_path)
    if dirty_kind == "tracked":
        (repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
    else:
        (repo / "untracked.txt").write_text("new\n", encoding="utf-8")

    receipt = verify_checkout(repo, head)

    assert receipt["status"] == "BLOCKED"
    assert receipt["available"] is True
    assert receipt["clean"] is False
    assert receipt["status_sha256"] != hashlib.sha256(b"").hexdigest()
    assert receipt["checks"]["clean"] is False
    assert receipt["errors"] == [
        {
            "code": "WORKTREE_DIRTY",
            "message": "tracked or untracked checkout changes are present",
        }
    ]


@pytest.mark.parametrize(
    "index_flag",
    ["--assume-unchanged", "--skip-worktree"],
)
def test_verify_checkout_blocks_index_flags_that_hide_worktree_changes(
    tmp_path: Path,
    index_flag: str,
) -> None:
    repo, head = _committed_repo(tmp_path)
    _git(repo, "update-index", index_flag, "tracked.txt")
    (repo / "tracked.txt").write_text("hidden change\n", encoding="utf-8")
    assert _git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""

    receipt = verify_checkout(repo, head)

    assert receipt["status"] == "BLOCKED"
    assert receipt["clean"] is False
    assert receipt["checks"]["index_visibility_unmodified"] is False
    assert receipt["errors"] == [
        {
            "code": "INDEX_VISIBILITY_WEAKENED",
            "message": (
                "Git index flags hide tracked worktree changes from status"
            ),
        }
    ]


def test_require_clean_false_relaxes_only_the_cleanliness_check(
    tmp_path: Path,
) -> None:
    repo, head = _committed_repo(tmp_path)
    (repo / "untracked.txt").write_text("new\n", encoding="utf-8")

    dirty_allowed = verify_checkout(repo, head, require_clean=False)
    wrong_head = verify_checkout(repo, "0" * 40, require_clean=False)

    assert dirty_allowed["status"] == "PASS"
    assert dirty_allowed["clean"] is False
    assert dirty_allowed["errors"] == []
    assert wrong_head["status"] == "BLOCKED"
    assert wrong_head["checks"]["head_matches"] is False
    assert wrong_head["errors"] == [
        {
            "code": "HEAD_MISMATCH",
            "message": "checkout HEAD does not match expected_head",
        }
    ]


def test_revision_path_binding_matches_exact_committed_blob(tmp_path: Path) -> None:
    repo, head = _committed_repo(tmp_path)
    observed = hashlib.sha256(
        (repo / "tracked.txt").read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()

    receipt = verify_paths_at_revision(repo, head, {"tracked.txt": observed})

    assert receipt["status"] == "PASS"
    assert receipt["path_count"] == receipt["matched_count"] == 1
    assert receipt["bindings"] == [
        {
            "path": "tracked.txt",
            "observed_sha256": observed,
            "revision_sha256": observed,
            "revision_blob_canonical": True,
            "matches": True,
        }
    ]
    assert receipt["errors"] == []


def test_revision_path_binding_rejects_coherent_worktree_aba_bytes(
    tmp_path: Path,
) -> None:
    repo, head = _committed_repo(tmp_path)
    modified = b"coherent but not committed\n"
    observed = hashlib.sha256(modified).hexdigest()

    receipt = verify_paths_at_revision(repo, head, {"tracked.txt": observed})

    assert receipt["status"] == "BLOCKED"
    assert receipt["path_count"] == 1
    assert receipt["matched_count"] == 0
    assert receipt["bindings"][0]["matches"] is False
    assert receipt["errors"][0]["code"] == "REVISION_BLOB_DIGEST_MISMATCH"


def test_revision_path_binding_ignores_git_replace_refs(tmp_path: Path) -> None:
    repo, head = _committed_repo(tmp_path)
    original_blob = _git(repo, "rev-parse", f"{head}:tracked.txt")
    replacement = b"replacement bytes\n"
    written = subprocess.run(
        ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
        input=replacement,
        check=True,
        capture_output=True,
    )
    replacement_blob = written.stdout.decode("ascii").strip()
    _git(repo, "replace", original_blob, replacement_blob)
    replacement_sha256 = hashlib.sha256(replacement).hexdigest()

    receipt = verify_paths_at_revision(
        repo, head, {"tracked.txt": replacement_sha256}
    )

    assert receipt["status"] == "BLOCKED"
    assert receipt["bindings"][0]["matches"] is False
    assert receipt["errors"][0]["code"] == "REVISION_BLOB_DIGEST_MISMATCH"


def test_revision_path_binding_rejects_noncanonical_crlf_revision_blob(
    tmp_path: Path,
) -> None:
    repo, _ = _committed_repo(tmp_path)
    _git(repo, "config", "core.autocrlf", "false")
    (repo / "tracked.txt").write_bytes(b"committed\r\n")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "--quiet", "-m", "noncanonical text blob")
    head = _git(repo, "rev-parse", "HEAD")
    lf_digest = hashlib.sha256(b"committed\n").hexdigest()

    receipt = verify_paths_at_revision(repo, head, {"tracked.txt": lf_digest})

    assert receipt["status"] == "BLOCKED"
    assert receipt["bindings"][0]["revision_blob_canonical"] is False
    assert receipt["bindings"][0]["matches"] is False
    assert receipt["errors"][0]["code"] == "REVISION_BLOB_NOT_CANONICAL"


def test_verify_checkout_fails_closed_when_git_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(git_state.subprocess, "run", unavailable)

    receipt = verify_checkout(tmp_path, "a" * 40)

    assert receipt["status"] == "BLOCKED"
    assert receipt["available"] is False
    assert receipt["head"] == "UNKNOWN"
    assert receipt["clean"] == "UNKNOWN"
    assert receipt["status_sha256"] == "UNKNOWN"
    assert receipt["checks"]["git_available"] is False
    assert receipt["errors"] == [
        {
            "code": "GIT_UNAVAILABLE",
            "message": "git executable is unavailable",
        }
    ]


def test_verify_checkout_fails_closed_on_git_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: dict[str, float] = {}

    def times_out(*args: object, timeout: float, **kwargs: object) -> None:
        observed["timeout"] = timeout
        raise subprocess.TimeoutExpired(cmd="git", timeout=timeout)

    monkeypatch.setattr(git_state.subprocess, "run", times_out)

    receipt = verify_checkout(tmp_path, "a" * 40)

    assert observed == {"timeout": 15.0}
    assert receipt["status"] == "BLOCKED"
    assert receipt["available"] is False
    assert receipt["errors"] == [
        {
            "code": "GIT_TIMEOUT",
            "message": "git command exceeded the 15 second timeout",
        }
    ]


def test_verify_checkout_fails_closed_on_non_utf8_git_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def invalid_utf8(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, stdout=b"\xff", stderr=b"")

    monkeypatch.setattr(git_state.subprocess, "run", invalid_utf8)

    receipt = verify_checkout(tmp_path, "a" * 40)

    assert receipt["status"] == "BLOCKED"
    assert receipt["available"] is False
    assert receipt["errors"] == [
        {
            "code": "GIT_OUTPUT_NOT_UTF8",
            "message": "git output is not valid UTF-8",
        }
    ]


@pytest.mark.parametrize("race_kind", ["head", "status"])
def test_verify_checkout_blocks_when_state_changes_during_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, race_kind: str
) -> None:
    head = "a" * 40
    outputs = [
        f"{tmp_path}\n".encode(),
        f"{head}\n".encode(),
        b"",
        b"H tracked.txt\0",
        (f"{'b' * 40}\n".encode() if race_kind == "head" else f"{head}\n".encode()),
        (b"?? raced.txt\n" if race_kind == "status" else b""),
        b"H tracked.txt\0",
    ]

    def changing_state(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, stdout=outputs.pop(0), stderr=b"")

    monkeypatch.setattr(git_state.subprocess, "run", changing_state)

    receipt = verify_checkout(tmp_path, head)

    assert receipt["status"] == "BLOCKED"
    assert receipt["observation"] == "AMBIGUOUS"
    assert receipt["available"] is False
    assert receipt["head"] == "UNKNOWN"
    assert receipt["clean"] == "UNKNOWN"
    assert receipt["status_sha256"] == "UNKNOWN"
    assert receipt["snapshots"] == {
        "start": {
            "head": head,
            "clean": True,
            "status_sha256": hashlib.sha256(b"").hexdigest(),
            "index_visibility_sha256": hashlib.sha256(
                b"H tracked.txt\0"
            ).hexdigest(),
        },
        "end": {
            "head": "b" * 40 if race_kind == "head" else head,
            "clean": race_kind != "status",
            "status_sha256": hashlib.sha256(
                b"?? raced.txt\n" if race_kind == "status" else b""
            ).hexdigest(),
            "index_visibility_sha256": hashlib.sha256(
                b"H tracked.txt\0"
            ).hexdigest(),
        },
    }
    assert receipt["checks"]["start_end_consistent"] is False
    assert receipt["errors"] == [
        {
            "code": "CHECKOUT_CHANGED_DURING_VERIFICATION",
            "message": "checkout HEAD or status changed during verification",
        }
    ]


def test_verify_checkout_rejects_a_noncanonical_observed_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = [
        f"{tmp_path}\n".encode(),
        ("A" * 40 + "\n").encode(),
        b"",
        b"H tracked.txt\0",
        ("A" * 40 + "\n").encode(),
        b"",
        b"H tracked.txt\0",
    ]

    def uppercase_head(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, stdout=outputs.pop(0), stderr=b"")

    monkeypatch.setattr(git_state.subprocess, "run", uppercase_head)

    receipt = verify_checkout(tmp_path, "a" * 40)

    assert receipt["status"] == "BLOCKED"
    assert receipt["available"] is False
    assert receipt["head"] == "UNKNOWN"
    assert receipt["errors"] == [
        {
            "code": "GIT_HEAD_INVALID",
            "message": "git HEAD is not an exact lowercase 40-character SHA",
        }
    ]


def test_native_observation_has_fixed_scope_and_exact_output_exclusions(
    tmp_path: Path,
) -> None:
    repo, _ = _committed_repo(tmp_path)
    native = repo / "src" / "Ariadne.AcadNative"
    dbx = repo / "src" / "Ariadne.AcadNativeDbx"
    reports = repo / "reports"
    for directory in (native, dbx, reports):
        directory.mkdir(parents=True)
    (native / "source.cpp").write_text("native\n", encoding="utf-8")
    (dbx / "source.cpp").write_text("dbx\n", encoding="utf-8")
    (reports / "status.json").write_text("{}\n", encoding="utf-8")
    _git(repo, "add", "src", "reports")
    _git(repo, "commit", "--quiet", "-m", "native sources")

    (reports / "status.json").write_text('{"changed":true}\n', encoding="utf-8")
    for root in (native, dbx):
        for output_component in ("bin", "obj", ".vs", "build", "obj-debug", "obj_cache"):
            output = root / output_component / "generated.obj"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("generated\n", encoding="utf-8")

    outputs_only = observe_native_source_checkout(repo)

    assert list(inspect.signature(observe_native_source_checkout).parameters) == [
        "repo_root"
    ]
    assert outputs_only["status"] == "PASS"
    assert outputs_only["available"] is True
    assert outputs_only["native_source_dirty"] is False
    assert outputs_only["native_source_status_sha256"] == hashlib.sha256(b"").hexdigest()
    assert outputs_only["checks"] == {
        "git_available": True,
        "index_visibility_unmodified": True,
        "start_end_consistent": True,
    }
    assert outputs_only["errors"] == []

    near_match = dbx / "objx" / "source.cpp"
    near_match.parent.mkdir()
    near_match.write_text("must remain source\n", encoding="utf-8")

    source_change = observe_native_source_checkout(repo)

    assert source_change["status"] == "PASS"
    assert source_change["native_source_dirty"] is True
    assert source_change["native_source_status_sha256"] != hashlib.sha256(b"").hexdigest()


@pytest.mark.parametrize(
    "index_flag",
    ["--assume-unchanged", "--skip-worktree"],
)
def test_native_observation_blocks_index_flags_that_hide_source_changes(
    tmp_path: Path,
    index_flag: str,
) -> None:
    repo, _ = _committed_repo(tmp_path)
    native = repo / "src" / "Ariadne.AcadNative"
    native.mkdir(parents=True)
    source = native / "probe.cpp"
    source.write_text("original\n", encoding="utf-8")
    _git(repo, "add", "src/Ariadne.AcadNative/probe.cpp")
    _git(repo, "commit", "--quiet", "-m", "native probe")
    _git(repo, "update-index", index_flag, "src/Ariadne.AcadNative/probe.cpp")
    source.write_text("hidden\n", encoding="utf-8")

    receipt = observe_native_source_checkout(repo)

    assert receipt["status"] == "BLOCKED"
    assert receipt["native_source_dirty"] == "UNKNOWN"
    assert receipt["checks"]["index_visibility_unmodified"] is False
    assert receipt["errors"] == [
        {
            "code": "INDEX_VISIBILITY_WEAKENED",
            "message": (
                "Git index flags hide native source changes from scoped status"
            ),
        }
    ]


def test_native_observation_does_not_publish_single_values_for_a_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    head = "a" * 40
    outputs = [
        f"{tmp_path}\n".encode(),
        f"{head}\n".encode(),
        b"",
        b"H src/Ariadne.AcadNative/source.cpp\0",
        f"{head}\n".encode(),
        b"?? src/Ariadne.AcadNative/source.cpp\n",
        b"H src/Ariadne.AcadNative/source.cpp\0",
    ]

    def changing_native_state(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, stdout=outputs.pop(0), stderr=b"")

    monkeypatch.setattr(git_state.subprocess, "run", changing_native_state)

    receipt = observe_native_source_checkout(tmp_path)

    assert receipt["status"] == "BLOCKED"
    assert receipt["observation"] == "AMBIGUOUS"
    assert receipt["available"] is False
    assert receipt["head"] == "UNKNOWN"
    assert receipt["native_source_dirty"] == "UNKNOWN"
    assert receipt["native_source_status_sha256"] == "UNKNOWN"
    assert receipt["snapshots"]["start"]["native_source_dirty"] is False
    assert receipt["snapshots"]["end"]["native_source_dirty"] is True
