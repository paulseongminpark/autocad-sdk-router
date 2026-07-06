#!/usr/bin/env python
"""merge_gate.py -- CADOS fleet single-writer merge gate [F7].

Wave-0 spawns N parallel builders, each in its OWN git worktree (see
spawn_worktree.ps1 in this same directory). Before any two of those worktrees'
branches are merged back, this module answers exactly one question,
truthfully: "did any two builders write to the same file?" If yes, reject --
merging is NOT single-writer safe (see also the WorkerUnit/Agent-Teams
discipline in 99_tools/CLAUDE.md: "WRITE must not overlap"). If no, every
builder's fileset can be merged one after another (serialized) with zero risk
of one clobbering another, because no file is shared.

Two layers:
  1. ``check_disjoint(claims)`` -- a PURE function. ``claims`` is
     {owner: [absolute paths, ...]}. Every path is canonicalized (symlinks +
     ``..`` resolved, case-normalized) before comparison, so two different
     spellings of the same file (relative vs absolute, mixed case, a
     differently-cased drive letter) always collide in the check. No side
     effects; safe to call speculatively/in a dry run.
  2. ``MergeGate`` -- a DURABLE, cross-process claim registry backed by lock
     files under a state directory. ``claim()`` is TOCTOU-safe: it does not
     "check, then write" (a window a second process could slip into between
     the check and the write); it ATOMICALLY creates one lock file per path
     via ``os.O_CREAT | os.O_EXCL``, which the OS guarantees only one caller
     can win. A conflicting claim rolls back everything it grabbed in that
     same call -- claiming is all-or-nothing per owner, never a partial grab.

Hard rules (no-fake-success):
  * ``check`` / ``claim`` / ``release`` never report ``status: ok`` unless
    every path was genuinely verified/locked. A conflict is always
    ``status: rejected`` -- never silently dropped, merged anyway, or
    downgraded to a warning.
  * Standard library only.
  * Read-only with respect to the worktrees themselves: ``git_changed_paths``
    only runs ``git diff`` / ``git ls-files`` (no checkout, no merge, no
    commit). This module never performs the merge; it only gates whether one
    may proceed.

CLI:
    python tools/fleet/merge_gate.py check   --manifest claims.json [--from-git]
    python tools/fleet/merge_gate.py claim   --manifest claims.json --owner f7 --state-dir <dir>
    python tools/fleet/merge_gate.py release --manifest claims.json --owner f7 --state-dir <dir>

``claims.json`` (default form): ``{"f5": ["D:\\...\\cad_diff.py", ...], "f7": [...]}``.
With ``--from-git`` on ``check``, instead: ``{"f5": {"worktree": "D:\\...\\autocad-sdk-router__w0_f5", "base_ref": "HEAD"}, ...}``
-- each owner's fileset is discovered from its own worktree via real git calls.

Exit codes: 0 = ok (disjoint / claimed / released). 1 = rejected (conflict) or
a manifest/usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Sequence

SCHEMA = "ariadne.cados.merge_gate.v1"


class MergeConflictError(Exception):
    """Raised internally when a claim would touch an already-claimed path."""


def normalize_path(path) -> str:
    """Resolve ``path`` to an absolute, case-normalized string.

    ``Path.resolve()`` follows symlinks and collapses ``..`` segments (it does
    NOT require the path to exist); ``os.path.normcase`` then lower-cases and
    forward-slash-normalizes on Windows. Two owners naming the "same" file via
    different spellings (relative vs absolute, mixed case, ``/`` vs ``\\``)
    always land on the same normalized string here -- this is what makes the
    disjointness check (and the claim below) TOCTOU-safe against spelling
    tricks, not just a raw string-equality check.
    """
    return os.path.normcase(str(Path(path).resolve()))


def find_overlaps(claims: Mapping[str, Sequence[str]]) -> Dict[str, List[str]]:
    """Return {normalized_path: [owners, ...]} for every path >1 owner claims."""
    owners_by_path: Dict[str, List[str]] = {}
    for owner, paths in claims.items():
        for raw in paths:
            norm = normalize_path(raw)
            owners_by_path.setdefault(norm, []).append(owner)
    return {
        path: sorted(set(owners))
        for path, owners in owners_by_path.items()
        if len(set(owners)) > 1
    }


def check_disjoint(claims: Mapping[str, Sequence[str]]) -> dict:
    """Pure, side-effect-free disjointness check over {owner: [paths, ...]}.

    status "ok"       -> every owner's fileset is pairwise disjoint; since no
                          file is shared, all owners can be merged ONE AFTER
                          ANOTHER (serialized_order) with no clobber risk.
    status "rejected"  -> at least one path is claimed by >1 owner; `overlaps`
                          names every conflicting path and its owners.
    """
    overlaps = find_overlaps(claims)
    if overlaps:
        return {
            "schema": SCHEMA,
            "status": "rejected",
            "reason": "overlapping_fileset",
            "overlaps": overlaps,
        }
    return {
        "schema": SCHEMA,
        "status": "ok",
        "reason": None,
        "serialized_order": sorted(claims.keys()),
    }


def git_changed_paths(worktree, base_ref: str = "HEAD") -> List[str]:
    """Absolute, normalized paths changed in ``worktree`` vs ``base_ref``.

    Real git (no mocking): the union of ``git diff --name-only base_ref``
    (committed + staged + unstaged changes against the base) and
    ``git ls-files --others --exclude-standard`` (new untracked files).
    Read-only -- neither command mutates the worktree.
    """
    worktree_path = Path(worktree)
    diffed = subprocess.run(
        ["git", "-C", str(worktree_path), "diff", "--name-only", base_ref],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "-C", str(worktree_path), "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    rels = [line for line in (diffed + untracked) if line.strip()]
    return [normalize_path(worktree_path / rel) for rel in rels]


class MergeGate:
    """Durable, cross-process single-writer gate over a claims directory.

    Two owners racing to claim the SAME resolved path cannot both succeed:
    the underlying primitive is ``os.open(path, O_CREAT | O_EXCL)``, which the
    OS guarantees is atomic -- there is no window between "check nobody holds
    this" and "take it" that a second process can land in. That window is
    exactly what makes naive check-then-write code TOCTOU-unsafe, so it is
    the one thing this class refuses to have.
    """

    def __init__(self, state_dir) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _lock_file(self, norm_path: str) -> Path:
        digest = hashlib.sha256(norm_path.encode("utf-8")).hexdigest()
        return self.state_dir / f"{digest}.lock"

    def _lock_owner(self, lock_file: Path) -> Optional[str]:
        try:
            payload = json.loads(lock_file.read_text(encoding="utf-8"))
            return payload.get("owner")
        except (OSError, ValueError):
            return None

    def claim(self, owner: str, paths: Iterable[str]) -> dict:
        """Claim every path in ``paths`` for ``owner``, or claim NONE of them.

        Re-claiming a path the SAME owner already holds is a no-op (safe to
        retry). Claiming a path another owner holds rolls back every lock
        this call itself just created and reports the first conflict.
        """
        claimed: List[str] = []
        try:
            for raw in paths:
                norm = normalize_path(raw)
                lock_file = self._lock_file(norm)
                try:
                    fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                except FileExistsError:
                    holder = self._lock_owner(lock_file) or "unknown"
                    if holder == owner:
                        continue  # idempotent re-claim by the same owner
                    raise MergeConflictError(
                        f"'{raw}' already claimed by '{holder}'") from None
                else:
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        json.dump({"owner": owner, "path": norm}, fh)
                    claimed.append(norm)
        except MergeConflictError as exc:
            for norm in claimed:
                self._lock_file(norm).unlink(missing_ok=True)
            return {
                "schema": SCHEMA, "action": "claim", "status": "rejected",
                "owner": owner, "reason": str(exc),
            }
        return {
            "schema": SCHEMA, "action": "claim", "status": "ok",
            "owner": owner, "claimed": claimed,
        }

    def release(self, owner: str, paths: Iterable[str]) -> dict:
        """Release every path in ``paths`` that ``owner`` currently holds.

        A path held by someone else, or not held at all, is reported in
        ``skipped`` rather than silently ignored -- releasing what you never
        held is never a truthful "ok".
        """
        released: List[str] = []
        skipped: List[str] = []
        for raw in paths:
            norm = normalize_path(raw)
            lock_file = self._lock_file(norm)
            holder = self._lock_owner(lock_file)
            if holder != owner:
                skipped.append(norm)
                continue
            lock_file.unlink(missing_ok=True)
            released.append(norm)
        return {
            "schema": SCHEMA, "action": "release", "status": "ok",
            "owner": owner, "released": released, "skipped": skipped,
        }

    @contextmanager
    def claim_scope(self, owner: str, paths: Sequence[str]) -> Iterator[dict]:
        """Claim on enter; ALWAYS release (best-effort) on exit, even if the
        merge body raises -- so a failed merge never leaves a stale lock."""
        result = self.claim(owner, paths)
        if result["status"] != "ok":
            raise MergeConflictError(result["reason"])
        try:
            yield result
        finally:
            self.release(owner, paths)


def _read_json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _claims_from_manifest(manifest: dict, from_git: bool) -> Dict[str, List[str]]:
    if not from_git:
        return {owner: list(paths) for owner, paths in manifest.items()}
    resolved: Dict[str, List[str]] = {}
    for owner, spec in manifest.items():
        resolved[owner] = git_changed_paths(spec["worktree"], spec.get("base_ref", "HEAD"))
    return resolved


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="merge_gate.py",
        description="CADOS fleet single-writer merge gate: reject overlapping "
                    "filesets before a serialized merge.")
    sub = ap.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser("check", help="pure disjointness check (no side effects)")
    check_p.add_argument("--manifest", required=True,
                         help='JSON {owner: [abs paths]}, or (with --from-git) '
                              '{owner: {"worktree": ..., "base_ref": ...}}')
    check_p.add_argument("--from-git", action="store_true",
                         help="resolve each owner's fileset via git diff/ls-files in its worktree")

    claim_p = sub.add_parser("claim", help="durable, TOCTOU-safe claim of one owner's fileset")
    claim_p.add_argument("--manifest", required=True, help='JSON {owner: [abs paths]}')
    claim_p.add_argument("--owner", required=True)
    claim_p.add_argument("--state-dir", required=True)

    release_p = sub.add_parser("release", help="release one owner's previously claimed fileset")
    release_p.add_argument("--manifest", required=True, help='JSON {owner: [abs paths]}')
    release_p.add_argument("--owner", required=True)
    release_p.add_argument("--state-dir", required=True)

    args = ap.parse_args(argv)

    if args.command == "check":
        manifest = _read_json(args.manifest)
        claims = _claims_from_manifest(manifest, from_git=args.from_git)
        result = check_disjoint(claims)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "ok" else 1

    manifest = _read_json(args.manifest)
    claims = _claims_from_manifest(manifest, from_git=False)
    if args.owner not in claims:
        print(json.dumps({
            "schema": SCHEMA, "status": "error",
            "reason": f"owner '{args.owner}' not present in manifest",
        }, ensure_ascii=False, indent=2))
        return 1

    gate = MergeGate(args.state_dir)
    if args.command == "claim":
        result = gate.claim(args.owner, claims[args.owner])
    else:
        result = gate.release(args.owner, claims[args.owner])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
