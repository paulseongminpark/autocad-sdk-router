#!/usr/bin/env python
"""Read-only gate for retiring a linked Git worktree.

The gate never removes a worktree or deletes a branch.  It answers one
question: has this secondary worktree reached the mechanically safe end of
its lifecycle?  PASS requires the worktree to be registered, unlocked,
clean, stable for the duration of the observation, and for its HEAD content
to be integrated into main (ancestry or patch equivalence) or verified on an
explicit remote archive ref.

Semantic reconciliation happens before this gate: stale material is removed,
while material worth keeping is merged to main or represented by a durable
preservation receipt that is itself merged to main.  A local branch alone is
not preservation and a clean worktree alone is not proof of merge.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


SCHEMA = "ariadne.cados.worktree_retirement.v1"
_GIT_TIMEOUT_SECONDS = 15


class GitObservationError(RuntimeError):
    """A required read-only Git observation could not be completed."""


def _git_env() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    env.update(
        {
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return env


def _run_git(
    worktree: Path,
    *args: str,
    allowed_returncodes: Sequence[int] = (0,),
) -> subprocess.CompletedProcess[bytes]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(worktree), *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
            env=_git_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitObservationError(f"git observation failed: {exc}") from exc
    if proc.returncode not in allowed_returncodes:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise GitObservationError(
            f"git {' '.join(args)} exited {proc.returncode}: {stderr}"
        )
    stderr = proc.stderr.decode("utf-8", errors="replace").strip()
    if stderr:
        raise GitObservationError(
            f"git {' '.join(args)} emitted stderr; observation is incomplete: {stderr}"
        )
    return proc


def _text(proc: subprocess.CompletedProcess[bytes]) -> str:
    return proc.stdout.decode("utf-8", errors="strict").strip()


def _canonical(path: str | Path) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def _remote_commit_for_tracking_ref(worktree: Path, ref: str) -> str:
    remotes = _text(_run_git(worktree, "remote")).splitlines()
    matches = [remote for remote in remotes if ref.startswith(f"refs/remotes/{remote}/")]
    if not matches:
        raise GitObservationError(
            f"no configured remote owns preservation ref '{ref}'"
        )
    remote = max(matches, key=len)
    branch = ref[len(f"refs/remotes/{remote}/") :]
    if not branch:
        raise GitObservationError(f"preservation ref has no branch component: '{ref}'")
    output = _text(
        _run_git(
            worktree,
            "ls-remote",
            "--exit-code",
            remote,
            f"refs/heads/{branch}",
        )
    )
    lines = output.splitlines()
    if len(lines) != 1:
        raise GitObservationError(
            f"remote preservation ref did not resolve exactly once: '{ref}'"
        )
    fields = lines[0].split()
    if len(fields) != 2 or fields[1] != f"refs/heads/{branch}":
        raise GitObservationError(f"unexpected ls-remote result for '{ref}'")
    return fields[0]


def _nul_paths(raw: bytes) -> list[str]:
    return [
        field.decode("utf-8", errors="strict")
        for field in raw.split(b"\0")
        if field
    ]


def _worktree_records(worktree: Path) -> list[dict[str, object]]:
    raw = _run_git(worktree, "worktree", "list", "--porcelain", "-z").stdout
    records: list[dict[str, object]] = []
    current: Optional[dict[str, object]] = None
    for field_bytes in raw.split(b"\0"):
        if not field_bytes:
            continue
        field = field_bytes.decode("utf-8", errors="strict")
        if field.startswith("worktree "):
            if current is not None:
                records.append(current)
            current = {
                "path": field[len("worktree ") :],
                "locked": False,
            }
        elif current is not None and field == "locked":
            current["locked"] = True
        elif current is not None and field.startswith("locked "):
            current["locked"] = True
            current["lock_reason"] = field[len("locked ") :]
        elif current is not None and field.startswith("HEAD "):
            current["head"] = field[len("HEAD ") :]
        elif current is not None and field.startswith("branch "):
            current["branch"] = field[len("branch ") :]
        elif current is not None and field == "detached":
            current["detached"] = True
    if current is not None:
        records.append(current)
    return records


def _snapshot(
    worktree: Path,
    main_ref: str,
    preservation_ref: Optional[str] = None,
) -> dict[str, object]:
    head = _text(_run_git(worktree, "rev-parse", "HEAD"))
    main_commit = _text(_run_git(worktree, "rev-parse", f"{main_ref}^{{commit}}"))
    preservation_commit = (
        None
        if preservation_ref is None
        else _text(
            _run_git(worktree, "rev-parse", f"{preservation_ref}^{{commit}}")
        )
    )
    status = _run_git(
        worktree,
        "status",
        "--porcelain=v2",
        "-z",
        "--untracked-files=all",
    ).stdout
    tracked_changes = _run_git(
        worktree,
        "diff",
        "--name-only",
        "-z",
        "HEAD",
    ).stdout
    untracked_changes = _run_git(
        worktree,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    ).stdout
    dirty_paths = sorted(set(_nul_paths(tracked_changes) + _nul_paths(untracked_changes)))
    ignored_paths = sorted(
        set(
            _nul_paths(
                _run_git(
                    worktree,
                    "ls-files",
                    "--others",
                    "--ignored",
                    "--exclude-standard",
                    "-z",
                ).stdout
            )
        )
    )
    visibility_entries = _nul_paths(
        _run_git(worktree, "ls-files", "-v", "-z").stdout
    )
    weakened_index_entries = sorted(
        entry
        for entry in visibility_entries
        if entry and (entry[0] == "S" or entry[0].islower())
    )
    records = _worktree_records(worktree)
    return {
        "head": head,
        "main_commit": main_commit,
        "preservation_commit": preservation_commit,
        "status": status,
        "dirty_paths": dirty_paths,
        "ignored_paths": ignored_paths,
        "weakened_index_entries": weakened_index_entries,
        "records": records,
    }


def check_retirement(
    worktree: str | Path,
    main_ref: str = "origin/main",
    preservation_ref: Optional[str] = None,
) -> dict:
    """Return a fail-closed retirement receipt without mutating Git state."""
    requested = Path(worktree)
    try:
        resolved = requested.resolve(strict=True)
    except OSError as exc:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "eligible_for_removal": False,
            "worktree": str(requested),
            "main_ref": main_ref,
            "checks": {},
            "reason_codes": ["WORKTREE_PATH_INVALID"],
            "errors": [str(exc)],
        }

    try:
        _run_git(resolved, "rev-parse", f"{main_ref}^{{commit}}")
    except GitObservationError as exc:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "eligible_for_removal": False,
            "worktree": str(resolved),
            "main_ref": main_ref,
            "checks": {"main_ref_resolved": False},
            "reason_codes": ["MAIN_REF_NOT_FOUND"],
            "errors": [str(exc)],
        }

    if preservation_ref is not None:
        if not preservation_ref.startswith("refs/remotes/"):
            return {
                "schema": SCHEMA,
                "status": "BLOCKED",
                "eligible_for_removal": False,
                "worktree": str(resolved),
                "main_ref": main_ref,
                "preservation_ref": preservation_ref,
                "checks": {"preservation_ref_is_remote_tracking": False},
                "reason_codes": ["PRESERVATION_REF_NOT_REMOTE_TRACKING"],
                "errors": [],
            }
        try:
            _run_git(resolved, "rev-parse", f"{preservation_ref}^{{commit}}")
        except GitObservationError as exc:
            return {
                "schema": SCHEMA,
                "status": "BLOCKED",
                "eligible_for_removal": False,
                "worktree": str(resolved),
                "main_ref": main_ref,
                "preservation_ref": preservation_ref,
                "checks": {"preservation_ref_resolved": False},
                "reason_codes": ["PRESERVATION_REF_NOT_FOUND"],
                "errors": [str(exc)],
            }
        try:
            preservation_remote_start = _remote_commit_for_tracking_ref(
                resolved, preservation_ref
            )
            preservation_local_start = _text(
                _run_git(resolved, "rev-parse", f"{preservation_ref}^{{commit}}")
            )
            if preservation_remote_start != preservation_local_start:
                raise GitObservationError(
                    "remote preservation commit differs from the local tracking ref"
                )
        except GitObservationError as exc:
            return {
                "schema": SCHEMA,
                "status": "BLOCKED",
                "eligible_for_removal": False,
                "worktree": str(resolved),
                "main_ref": main_ref,
                "preservation_ref": preservation_ref,
                "checks": {"preservation_remote_verified": False},
                "reason_codes": ["PRESERVATION_REMOTE_UNVERIFIED"],
                "errors": [str(exc)],
            }
    else:
        preservation_remote_start = None

    try:
        start = _snapshot(resolved, main_ref, preservation_ref)
        common_dir = Path(
            _text(
                _run_git(
                    resolved,
                    "rev-parse",
                    "--path-format=absolute",
                    "--git-common-dir",
                )
            )
        ).resolve(strict=True)
        primary = common_dir.parent
        normalized = _canonical(resolved)
        record = next(
            (
                item
                for item in start["records"]
                if _canonical(str(item["path"])) == normalized
            ),
            None,
        )
        merged_proc = _run_git(
            resolved,
            "merge-base",
            "--is-ancestor",
            str(start["head"]),
            str(start["main_commit"]),
            allowed_returncodes=(0, 1),
        )
        cherry_lines_text = _text(
            _run_git(resolved, "cherry", str(start["main_commit"]), str(start["head"]))
        )
        cherry_lines = cherry_lines_text.splitlines() if cherry_lines_text else []
        unique_commits = [line[2:] for line in cherry_lines if line.startswith("+ ")]
        equivalent_commits = [line[2:] for line in cherry_lines if line.startswith("- ")]
        merge_commits_text = _text(
            _run_git(
                resolved,
                "rev-list",
                "--reverse",
                "--merges",
                f"{start['main_commit']}..{start['head']}",
            )
        )
        unresolved_merge_commits = (
            merge_commits_text.splitlines() if merge_commits_text else []
        )
        patch_equivalent = not unique_commits and not unresolved_merge_commits
        if preservation_ref is None:
            preserved = False
        else:
            preserved = _run_git(
                resolved,
                "merge-base",
                "--is-ancestor",
                str(start["head"]),
                str(start["preservation_commit"]),
                allowed_returncodes=(0, 1),
            ).returncode == 0
        end = _snapshot(resolved, main_ref, preservation_ref)
        preservation_remote_end = (
            None
            if preservation_ref is None
            else _remote_commit_for_tracking_ref(resolved, preservation_ref)
        )
    except (GitObservationError, OSError, UnicodeError) as exc:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "eligible_for_removal": False,
            "worktree": str(requested),
            "main_ref": main_ref,
            "checks": {},
            "reason_codes": ["GIT_OBSERVATION_FAILED"],
            "errors": [str(exc)],
        }

    checks = {
        "registered": record is not None,
        "secondary_worktree": normalized != _canonical(primary),
        "unlocked": record is not None and not bool(record.get("locked", False)),
        "clean": start["status"] == b"",
        "ignored_content_absent": not start["ignored_paths"],
        "index_visibility_intact": not start["weakened_index_entries"],
        "head_merged_to_main": merged_proc.returncode == 0,
        "patch_equivalent_to_main": patch_equivalent,
        "head_preserved": preserved,
        "head_reconciled": merged_proc.returncode == 0 or patch_equivalent or preserved,
        "snapshot_stable": (
            start == end and preservation_remote_start == preservation_remote_end
        ),
    }
    reason_by_check = {
        "registered": "WORKTREE_NOT_REGISTERED",
        "secondary_worktree": "PRIMARY_WORKTREE_NOT_REMOVABLE",
        "unlocked": "WORKTREE_LOCKED",
        "clean": "WORKTREE_DIRTY",
        "ignored_content_absent": "IGNORED_CONTENT_PRESENT",
        "index_visibility_intact": "INDEX_VISIBILITY_WEAKENED",
        "head_reconciled": "HEAD_NOT_MERGED_OR_PRESERVED",
        "snapshot_stable": "CHECKOUT_CHANGED_DURING_VERIFICATION",
    }
    reasons = [
        reason_by_check[name]
        for name, passed in checks.items()
        if not passed and name in reason_by_check
    ]
    eligible = not reasons
    return {
        "schema": SCHEMA,
        "status": "PASS" if eligible else "BLOCKED",
        "eligible_for_removal": eligible,
        "worktree": str(resolved),
        "main_ref": main_ref,
        "head": start["head"],
        "main_commit": start["main_commit"],
        "branch": None if record is None else record.get("branch"),
        "checks": checks,
        "reason_codes": reasons,
        "observations": {
            "unique_commits": unique_commits,
            "patch_equivalent_commits": equivalent_commits,
            "unresolved_merge_commits": unresolved_merge_commits,
            "dirty_paths": start["dirty_paths"],
            "ignored_paths": start["ignored_paths"],
            "lock_reason": None if record is None else record.get("lock_reason"),
            "weakened_index_entries": start["weakened_index_entries"],
            "preservation_ref": preservation_ref,
            "preservation_commit": start["preservation_commit"],
            "preservation_remote_commit": preservation_remote_start,
        },
        "limitations": [
            "semantic_staleness_and_external_preservation_require_human_disposition_before_clean_state"
        ],
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="retirement_gate.py",
        description="Read-only gate: a worktree may be removed only after clean merge closure.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="emit a retirement eligibility receipt")
    check.add_argument("--worktree", required=True)
    check.add_argument("--main-ref", default="origin/main")
    check.add_argument(
        "--preservation-ref",
        help="optional refs/remotes/... archive ref that contains the exact worktree HEAD",
    )
    args = parser.parse_args(argv)

    receipt = check_retirement(
        args.worktree,
        main_ref=args.main_ref,
        preservation_ref=args.preservation_ref,
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
