"""F7 TEST -- fleet merge_gate: single-writer, TOCTOU-safe, disjoint-fileset gate.

Intent (WHY):
  * check_disjoint() is the thing that decides whether Wave-0's parallel
    worktrees can be merged back one after another without a silent clobber.
    It MUST reject on the first shared path, and it MUST catch that path even
    when two owners spell it differently (relative/absolute, mixed case,
    forward vs back slash) -- a gate a builder can dodge by respelling a path
    is not a gate.
  * MergeGate.claim() is the durable half: two owners racing for the same
    path from separate calls/processes must not both win, and a rejected
    claim must not leave a partial lock behind for paths it DID grab earlier
    in that same call (all-or-nothing). This is what "TOCTOU-safe" means
    operationally here, not just "resolves paths".
  * git_changed_paths() is the real (non-mocked) source of a builder's
    fileset in normal fleet use: a worktree's committed+staged+unstaged diff
    against its base ref, plus any new untracked files.

No CAD runtime involved anywhere in this file -- git and the filesystem are
the only externals, and both are exercised for real (a scratch git repo is
`git init`-ed on disk per test; nothing here is mocked).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_THIS = Path(__file__).resolve()
_REPO = _THIS.parents[2]
_FLEET_DIR = _REPO / "tools" / "fleet"
for _p in (_REPO, _REPO / "tools", _FLEET_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import merge_gate  # noqa: E402


# --------------------------------------------------------------------------- #
# check_disjoint -- pure, no side effects
# --------------------------------------------------------------------------- #

def test_check_disjoint_two_disjoint_filesets_ok_serialized(tmp_path):
    f5_file = tmp_path / "f5" / "cad_diff.py"
    f7_file = tmp_path / "f7" / "merge_gate.py"
    f5_file.parent.mkdir(parents=True)
    f7_file.parent.mkdir(parents=True)
    f5_file.write_text("f5")
    f7_file.write_text("f7")

    result = merge_gate.check_disjoint({
        "f5": [str(f5_file)],
        "f7": [str(f7_file)],
    })

    assert result["status"] == "ok"
    assert result["reason"] is None
    assert result["serialized_order"] == ["f5", "f7"]


def test_check_disjoint_overlapping_filesets_rejected(tmp_path):
    shared = tmp_path / "tools" / "cad_diff.py"
    shared.parent.mkdir(parents=True)
    shared.write_text("shared")

    result = merge_gate.check_disjoint({
        "f5": [str(shared)],
        "f9": [str(shared)],
    })

    assert result["status"] == "rejected"
    assert result["reason"] == "overlapping_fileset"
    [owners] = result["overlaps"].values()
    assert sorted(owners) == ["f5", "f9"]


def test_check_disjoint_normalizes_case_and_slash_spelling(tmp_path):
    """Same real file, claimed via two different spellings -> still caught.

    This is the property that makes the gate resistant to a builder dodging
    the check by naming a path slightly differently than its conflicting
    sibling (mixed case, forward vs back slash) rather than an actual
    different file.
    """
    real = tmp_path / "tools" / "shared.py"
    real.parent.mkdir(parents=True)
    real.write_text("shared")
    upper_spelling = str(real).upper()
    forward_slash_spelling = str(real).replace("\\", "/")

    result = merge_gate.check_disjoint({
        "f5": [upper_spelling],
        "f9": [forward_slash_spelling],
    })

    assert result["status"] == "rejected"
    [owners] = result["overlaps"].values()
    assert sorted(owners) == ["f5", "f9"]


def test_check_disjoint_same_owner_repeating_own_path_is_not_a_conflict(tmp_path):
    own = tmp_path / "tools" / "spawn_worktree.ps1"
    own.parent.mkdir(parents=True)
    own.write_text("own")

    result = merge_gate.check_disjoint({"f7": [str(own), str(own)]})

    assert result["status"] == "ok"


# --------------------------------------------------------------------------- #
# MergeGate -- durable, TOCTOU-safe claim/release
# --------------------------------------------------------------------------- #

def test_mergegate_claim_atomic_second_claimant_rejected_without_partial_leak(tmp_path):
    x = tmp_path / "x.py"
    y = tmp_path / "y.py"
    x.write_text("x")
    y.write_text("y")
    gate = merge_gate.MergeGate(tmp_path / "state")

    first = gate.claim("f5", [str(x)])
    assert first["status"] == "ok"

    # f9 asks for y (free) AND x (already f5's) in one call, y first so a
    # non-atomic implementation would grab y before failing on x.
    second = gate.claim("f9", [str(y), str(x)])
    assert second["status"] == "rejected"
    assert "f5" in second["reason"]

    # f9's rejected attempt must not have left y claimed -- a third owner can
    # still take it. If claim() leaked the partial grab of y, this would
    # reject too.
    third = gate.claim("modprobe", [str(y)])
    assert third["status"] == "ok"


def test_mergegate_reclaim_by_same_owner_is_idempotent(tmp_path):
    x = tmp_path / "x.py"
    x.write_text("x")
    gate = merge_gate.MergeGate(tmp_path / "state")

    assert gate.claim("f5", [str(x)])["status"] == "ok"
    again = gate.claim("f5", [str(x)])
    assert again["status"] == "ok"


def test_mergegate_release_frees_lock_for_a_different_owner(tmp_path):
    x = tmp_path / "x.py"
    x.write_text("x")
    gate = merge_gate.MergeGate(tmp_path / "state")

    gate.claim("f5", [str(x)])
    blocked = gate.claim("f9", [str(x)])
    assert blocked["status"] == "rejected"

    released = gate.release("f5", [str(x)])
    assert released["status"] == "ok"
    assert released["skipped"] == []

    now_ok = gate.claim("f9", [str(x)])
    assert now_ok["status"] == "ok"


def test_mergegate_release_by_non_holder_is_skipped_not_faked(tmp_path):
    x = tmp_path / "x.py"
    x.write_text("x")
    gate = merge_gate.MergeGate(tmp_path / "state")
    gate.claim("f5", [str(x)])

    result = gate.release("f9", [str(x)])

    assert result["status"] == "ok"    # the release call itself didn't error...
    assert result["released"] == []    # ...but it truthfully released nothing
    assert len(result["skipped"]) == 1
    assert gate.claim("f9", [str(x)])["status"] == "rejected"  # f5 still holds it


def test_mergegate_claim_scope_releases_even_when_body_raises(tmp_path):
    x = tmp_path / "x.py"
    x.write_text("x")
    gate = merge_gate.MergeGate(tmp_path / "state")

    with pytest.raises(RuntimeError):
        with gate.claim_scope("f5", [str(x)]):
            raise RuntimeError("merge step blew up")

    assert gate.claim("f9", [str(x)])["status"] == "ok"  # released despite the raise


def test_mergegate_claim_scope_conflict_raises_mergeconflicterror(tmp_path):
    x = tmp_path / "x.py"
    x.write_text("x")
    gate = merge_gate.MergeGate(tmp_path / "state")
    gate.claim("f5", [str(x)])

    with pytest.raises(merge_gate.MergeConflictError):
        with gate.claim_scope("f9", [str(x)]):
            pytest.fail("body must not run when the claim is rejected")


# --------------------------------------------------------------------------- #
# git_changed_paths -- real git, no mocking
# --------------------------------------------------------------------------- #

def _run_git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


@pytest.fixture
def scratch_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git("init", "--quiet", "-b", "main", cwd=repo)
    _run_git("config", "user.email", "test@example.invalid", cwd=repo)
    _run_git("config", "user.name", "Merge Gate Test", cwd=repo)
    (repo / "base.py").write_text("base\n")
    _run_git("add", "base.py", cwd=repo)
    _run_git("commit", "--quiet", "-m", "base", cwd=repo)
    return repo


def test_git_changed_paths_reports_modified_and_untracked_files(scratch_git_repo):
    (scratch_git_repo / "base.py").write_text("base\nchanged\n")
    (scratch_git_repo / "new_untracked.py").write_text("new\n")

    changed = merge_gate.git_changed_paths(str(scratch_git_repo), base_ref="HEAD")

    expected = {
        merge_gate.normalize_path(scratch_git_repo / "base.py"),
        merge_gate.normalize_path(scratch_git_repo / "new_untracked.py"),
    }
    assert set(changed) == expected


def test_git_changed_paths_two_worktrees_feed_a_real_disjoint_check(scratch_git_repo):
    """End-to-end: two owners' REAL git filesets, fed straight into
    check_disjoint(), agree they are disjoint -- exactly like two Wave-0
    worktrees would if they touched different files."""
    (scratch_git_repo / "base.py").write_text("base\nf5 change\n")
    (scratch_git_repo / "f7_only.py").write_text("f7\n")

    all_changed = merge_gate.git_changed_paths(str(scratch_git_repo))
    claims = {
        "f5": [p for p in all_changed if p.endswith("base.py")],
        "f7": [p for p in all_changed if p.endswith("f7_only.py")],
    }

    result = merge_gate.check_disjoint(claims)

    assert result["status"] == "ok"
    assert result["serialized_order"] == ["f5", "f7"]


# --------------------------------------------------------------------------- #
# CLI (subprocess, matches the cadctl_cli.py test convention in this suite)
# --------------------------------------------------------------------------- #

def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(_FLEET_DIR / "merge_gate.py"), *args],
        cwd=str(_REPO),
        text=True,
        capture_output=True,
    )


def test_cli_check_ok_exit_zero(tmp_path):
    manifest = tmp_path / "claims.json"
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("a")
    b.write_text("b")
    manifest.write_text(json.dumps({"f5": [str(a)], "f7": [str(b)]}))

    proc = _run_cli("check", "--manifest", str(manifest))

    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["schema"] == "ariadne.cados.merge_gate.v1"
    assert out["status"] == "ok"


def test_cli_check_overlap_exit_one(tmp_path):
    manifest = tmp_path / "claims.json"
    shared = tmp_path / "shared.py"
    shared.write_text("shared")
    manifest.write_text(json.dumps({"f5": [str(shared)], "f7": [str(shared)]}))

    proc = _run_cli("check", "--manifest", str(manifest))

    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["status"] == "rejected"


def test_cli_claim_then_release_roundtrip(tmp_path):
    manifest = tmp_path / "claims.json"
    x = tmp_path / "x.py"
    x.write_text("x")
    manifest.write_text(json.dumps({"f7": [str(x)]}))
    state_dir = tmp_path / "state"

    claimed = _run_cli("claim", "--manifest", str(manifest), "--owner", "f7", "--state-dir", str(state_dir))
    assert claimed.returncode == 0, claimed.stderr
    assert json.loads(claimed.stdout)["status"] == "ok"

    released = _run_cli("release", "--manifest", str(manifest), "--owner", "f7", "--state-dir", str(state_dir))
    assert released.returncode == 0, released.stderr
    assert json.loads(released.stdout)["status"] == "ok"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
