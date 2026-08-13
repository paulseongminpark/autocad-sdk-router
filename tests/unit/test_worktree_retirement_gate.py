"""Worktree retirement is allowed only after content reconciliation and merge.

The public seam is the read-only CLI in ``tools/fleet/retirement_gate.py``.
Tests use real Git repositories and linked worktrees; no Git behavior is mocked.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


_THIS = Path(__file__).resolve()
_REPO = _THIS.parents[2]
_GATE = _REPO / "tools" / "fleet" / "retirement_gate.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _commit_file(repo: Path, name: str, text: str, message: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "--quiet", "-m", message)


def _merged_feature_worktree(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    lane = tmp_path / "lane"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Retirement Gate Test")
    _commit_file(repo, "base.txt", "base\n", "base")
    _git(repo, "worktree", "add", "--quiet", "-b", "feature", str(lane))
    _commit_file(lane, "feature.txt", "preserve me\n", "feature")
    _git(repo, "merge", "--quiet", "--no-ff", "feature", "-m", "merge feature")
    return repo, lane


def _unmerged_feature_worktree(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    lane = tmp_path / "lane"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Retirement Gate Test")
    _commit_file(repo, "base.txt", "base\n", "base")
    _git(repo, "worktree", "add", "--quiet", "-b", "feature", str(lane))
    _commit_file(lane, "feature.txt", "not merged yet\n", "feature")
    head = _git(lane, "rev-parse", "HEAD").stdout.strip()
    return repo, lane, head


def _run_gate(
    worktree: Path,
    main_ref: str = "main",
    preservation_ref: str | None = None,
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        str(_GATE),
        "check",
        "--worktree",
        str(worktree),
        "--main-ref",
        main_ref,
    ]
    if preservation_ref is not None:
        args.extend(["--preservation-ref", preservation_ref])
    return subprocess.run(
        args,
        cwd=str(_REPO),
        capture_output=True,
        text=True,
    )


def test_cli_passes_for_clean_unlocked_worktree_after_head_is_merged(tmp_path: Path) -> None:
    _repo, lane = _merged_feature_worktree(tmp_path)

    proc = _run_gate(lane)

    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(proc.stdout)
    assert receipt["schema"] == "ariadne.cados.worktree_retirement.v1"
    assert receipt["status"] == "PASS"
    assert receipt["eligible_for_removal"] is True
    assert receipt["reason_codes"] == []
    assert receipt["checks"] == {
        "registered": True,
        "secondary_worktree": True,
        "unlocked": True,
        "clean": True,
        "ignored_content_absent": True,
        "index_visibility_intact": True,
        "head_merged_to_main": True,
        "patch_equivalent_to_main": True,
        "head_preserved": False,
        "head_reconciled": True,
        "snapshot_stable": True,
    }


def test_cli_blocks_unmerged_head_and_reports_unique_commit(tmp_path: Path) -> None:
    _repo, lane, feature_head = _unmerged_feature_worktree(tmp_path)

    proc = _run_gate(lane)

    assert proc.returncode == 1
    receipt = json.loads(proc.stdout)
    assert receipt["status"] == "BLOCKED"
    assert receipt["eligible_for_removal"] is False
    assert receipt["checks"]["head_merged_to_main"] is False
    assert receipt["reason_codes"] == ["HEAD_NOT_MERGED_OR_PRESERVED"]
    assert receipt["observations"]["unique_commits"] == [feature_head]


def test_cli_accepts_patch_equivalent_commit_already_integrated_on_main(
    tmp_path: Path,
) -> None:
    repo, lane, _feature_head = _unmerged_feature_worktree(tmp_path)
    _git(repo, "cherry-pick", "--no-commit", "feature")
    _git(repo, "commit", "--quiet", "-m", "integrate equivalent patch")

    proc = _run_gate(lane)

    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(proc.stdout)
    assert receipt["status"] == "PASS"
    assert receipt["checks"]["head_merged_to_main"] is False
    assert receipt["checks"]["patch_equivalent_to_main"] is True
    assert receipt["checks"]["head_reconciled"] is True
    assert receipt["observations"]["unique_commits"] == []


def test_cli_rejects_forged_local_remote_tracking_ref_without_remote_proof(
    tmp_path: Path,
) -> None:
    repo, lane, feature_head = _unmerged_feature_worktree(tmp_path)
    _git(repo, "update-ref", "refs/remotes/origin/archive/feature", feature_head)

    proc = _run_gate(
        lane,
        preservation_ref="refs/remotes/origin/archive/feature",
    )

    assert proc.returncode == 1
    receipt = json.loads(proc.stdout)
    assert receipt["status"] == "BLOCKED"
    assert receipt["eligible_for_removal"] is False
    assert receipt["checks"] == {"preservation_remote_verified": False}
    assert receipt["reason_codes"] == ["PRESERVATION_REMOTE_UNVERIFIED"]


def test_cli_accepts_head_verified_on_remote_archive_ref(tmp_path: Path) -> None:
    repo, lane, feature_head = _unmerged_feature_worktree(tmp_path)
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "--quiet", "--bare")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "--quiet", "origin", "feature:refs/heads/archive/feature")
    _git(
        repo,
        "fetch",
        "--quiet",
        "origin",
        "refs/heads/archive/feature:refs/remotes/origin/archive/feature",
    )

    proc = _run_gate(
        lane,
        preservation_ref="refs/remotes/origin/archive/feature",
    )

    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(proc.stdout)
    assert receipt["status"] == "PASS"
    assert receipt["checks"]["head_merged_to_main"] is False
    assert receipt["checks"]["patch_equivalent_to_main"] is False
    assert receipt["checks"]["head_preserved"] is True
    assert receipt["checks"]["head_reconciled"] is True
    assert receipt["observations"]["preservation_commit"] == feature_head
    assert receipt["observations"]["preservation_remote_commit"] == feature_head


def test_cli_blocks_dirty_worktree_and_reports_paths_for_disposition(tmp_path: Path) -> None:
    _repo, lane = _merged_feature_worktree(tmp_path)
    (lane / "feature.txt").write_text("dirty tracked change\n", encoding="utf-8")
    (lane / "untracked-note.txt").write_text("classify me\n", encoding="utf-8")

    proc = _run_gate(lane)

    assert proc.returncode == 1
    receipt = json.loads(proc.stdout)
    assert receipt["status"] == "BLOCKED"
    assert receipt["checks"]["clean"] is False
    assert receipt["reason_codes"] == ["WORKTREE_DIRTY"]
    assert receipt["observations"]["dirty_paths"] == [
        "feature.txt",
        "untracked-note.txt",
    ]


def test_cli_blocks_ignored_content_that_would_be_lost_on_removal(tmp_path: Path) -> None:
    repo, lane = _merged_feature_worktree(tmp_path)
    (lane / ".gitignore").write_text("*.cache\n", encoding="utf-8")
    _git(lane, "add", ".gitignore")
    _git(lane, "commit", "--quiet", "-m", "ignore cache")
    _git(repo, "merge", "--quiet", "--no-ff", "feature", "-m", "merge ignore")
    (lane / "research.cache").write_text("unclassified evidence\n", encoding="utf-8")
    assert _git(lane, "status", "--porcelain").stdout == ""

    proc = _run_gate(lane)

    assert proc.returncode == 1
    receipt = json.loads(proc.stdout)
    assert receipt["status"] == "BLOCKED"
    assert receipt["checks"]["clean"] is True
    assert receipt["checks"]["ignored_content_absent"] is False
    assert receipt["reason_codes"] == ["IGNORED_CONTENT_PRESENT"]
    assert receipt["observations"]["ignored_paths"] == ["research.cache"]


def test_cli_blocks_locked_worktree_and_preserves_lock_reason(tmp_path: Path) -> None:
    repo, lane = _merged_feature_worktree(tmp_path)
    _git(repo, "worktree", "lock", "--reason", "awaiting evidence merge", str(lane))

    proc = _run_gate(lane)

    assert proc.returncode == 1
    receipt = json.loads(proc.stdout)
    assert receipt["status"] == "BLOCKED"
    assert receipt["checks"]["unlocked"] is False
    assert receipt["reason_codes"] == ["WORKTREE_LOCKED"]
    assert receipt["observations"]["lock_reason"] == "awaiting evidence merge"


@pytest.mark.parametrize(
    ("index_flag", "expected_tag"),
    [
        ("--assume-unchanged", "h"),
        ("--skip-worktree", "S"),
    ],
)
def test_cli_blocks_index_flags_that_hide_worktree_changes(
    tmp_path: Path,
    index_flag: str,
    expected_tag: str,
) -> None:
    _repo, lane = _merged_feature_worktree(tmp_path)
    _git(lane, "update-index", index_flag, "feature.txt")
    (lane / "feature.txt").write_text("hidden dirty bytes\n", encoding="utf-8")
    assert _git(lane, "status", "--porcelain").stdout == ""

    proc = _run_gate(lane)

    assert proc.returncode == 1
    receipt = json.loads(proc.stdout)
    assert receipt["status"] == "BLOCKED"
    assert receipt["checks"]["clean"] is True
    assert receipt["checks"]["index_visibility_intact"] is False
    assert receipt["reason_codes"] == ["INDEX_VISIBILITY_WEAKENED"]
    assert receipt["observations"]["weakened_index_entries"] == [
        f"{expected_tag} feature.txt"
    ]


def test_cli_blocks_when_main_ref_cannot_be_resolved(tmp_path: Path) -> None:
    _repo, lane = _merged_feature_worktree(tmp_path)

    proc = _run_gate(lane, main_ref="refs/heads/does-not-exist")

    assert proc.returncode == 1
    receipt = json.loads(proc.stdout)
    assert receipt["status"] == "BLOCKED"
    assert receipt["eligible_for_removal"] is False
    assert receipt["reason_codes"] == ["MAIN_REF_NOT_FOUND"]
    assert receipt["checks"] == {"main_ref_resolved": False}


def test_cli_blocks_when_git_warns_that_observation_is_incomplete(tmp_path: Path) -> None:
    _repo, lane = _merged_feature_worktree(tmp_path)
    _git(lane, "config", "core.fsmonitor", "definitely-missing-fsmonitor-command")
    probe = subprocess.run(
        ["git", "-C", str(lane), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0
    assert probe.stderr

    proc = _run_gate(lane)

    assert proc.returncode == 1
    receipt = json.loads(proc.stdout)
    assert receipt["status"] == "BLOCKED"
    assert receipt["eligible_for_removal"] is False
    assert receipt["reason_codes"] == ["GIT_OBSERVATION_FAILED"]
    assert "stderr" in receipt["errors"][0]
