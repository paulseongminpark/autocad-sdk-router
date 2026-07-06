#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cert_artifact_index.py -- deterministic inventory of cert evidence under
runs/ and attended_runs/ (codex-5.5-xhigh audit finding 6).

Every *.json file under any immediate run-directory of runs/ or
attended_runs/ is discovered by walking the filesystem (os.walk), never by
matching a hardcoded closed list of known filenames -- a new evidence
filename introduced by a future wave (e.g. a new cert report name) is still
picked up and classified by its own name, instead of being silently
skipped because nobody added it to a list here.

Each discovered artifact is reported as:
    {path, run_dir, scan_root, kind, sha256, byte_size, mtime,
     json_valid, json_error}

"kind" is the file's own stem (e.g. "summary", "regen_summary", "journal")
-- a label, not a classification scheme; this module makes no claim about
what a given filename MEANS, only that it exists and hashes to a given
value. json_valid/json_error come from actually parsing the file with a
utf-8-sig-tolerant decode (several JSON artifacts in this repo carry a
UTF-8 BOM from PowerShell writers -- see cados-architecture-contract) --
this catches a truncated/corrupted cert artifact that would otherwise look
fine under a byte-hash-only inventory.

Stdlib only. Read-only: never opens a target file for write, never mutates
runs/ or attended_runs/. Idempotent: rerunning overwrites the ONE output
report at --out with a freshly recomputed index; it does not accumulate
state anywhere.

CLI:
    python tools/cert_artifact_index.py
    python tools/cert_artifact_index.py --scan-root runs --out reports/cert_artifact_index.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)

DEFAULT_SCAN_ROOTS = ("runs", "attended_runs")
DEFAULT_OUT_PATH = os.path.join(_ROUTER_HOME, "reports", "cert_artifact_index.json")


def sha256_file(path: str) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _relpath(path: str, base: str) -> str:
    return os.path.relpath(path, base).replace(os.sep, "/")


def discover_run_dirs(scan_root: str) -> List[str]:
    """Every immediate child directory of ``scan_root`` (one cert evidence
    dir per run, e.g. runs/capstone_final_<ts>/) -- glob-based (os.listdir
    + isdir), not a hardcoded list of run names."""
    if not os.path.isdir(scan_root):
        return []
    return sorted(
        os.path.join(scan_root, name) for name in os.listdir(scan_root)
        if os.path.isdir(os.path.join(scan_root, name))
    )


def index_one_artifact(fpath: str, run_dir: str, scan_root_label: str, router_home: str) -> Dict[str, Any]:
    try:
        st = os.stat(fpath)
        byte_size, mtime = st.st_size, st.st_mtime
    except OSError:
        byte_size, mtime = None, None

    json_valid = True
    json_error = None
    try:
        with open(fpath, encoding="utf-8-sig") as fh:
            json.load(fh)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        json_valid = False
        json_error = "%s: %s" % (type(exc).__name__, exc)

    return {
        "path": _relpath(fpath, router_home),
        "run_dir": _relpath(run_dir, router_home),
        "scan_root": scan_root_label,
        "kind": os.path.splitext(os.path.basename(fpath))[0],
        "sha256": sha256_file(fpath),
        "byte_size": byte_size,
        "mtime": mtime,
        "json_valid": json_valid,
        "json_error": json_error,
    }


def scan_run_dir(run_dir: str, scan_root_label: str, router_home: str) -> List[Dict[str, Any]]:
    """Every *.json file anywhere under ``run_dir`` (os.walk -- covers
    nested evidence like regen/journal.json, regen/pre/dwg_graph_ir.json --
    never a hardcoded closed filename list), one record per file."""
    artifacts: List[Dict[str, Any]] = []
    for root, _dirs, files in os.walk(run_dir):
        for fname in sorted(files):
            if not fname.lower().endswith(".json"):
                continue
            artifacts.append(
                index_one_artifact(os.path.join(root, fname), run_dir, scan_root_label, router_home))
    return artifacts


def build_index(router_home: str = _ROUTER_HOME,
                scan_roots: Optional[List[str]] = None) -> Dict[str, Any]:
    artifacts: List[Dict[str, Any]] = []
    roots_scanned = []
    for root_name in (scan_roots if scan_roots is not None else DEFAULT_SCAN_ROOTS):
        root_path = os.path.join(router_home, root_name)
        exists = os.path.isdir(root_path)
        roots_scanned.append({"name": root_name, "path": _relpath(root_path, router_home), "exists": exists})
        for run_dir in discover_run_dirs(root_path):
            artifacts.extend(scan_run_dir(run_dir, root_name, router_home))
    artifacts.sort(key=lambda a: a["path"])
    invalid = [a for a in artifacts if not a["json_valid"]]
    return {
        "schema": "cert_artifact_index.v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "router_home": router_home,
        "scan_roots": roots_scanned,
        "artifact_count": len(artifacts),
        "invalid_count": len(invalid),
        "invalid_paths": [a["path"] for a in invalid],
        "artifacts": artifacts,
    }


def _write_json(path: str, obj: Any) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, default=str)
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic glob-based inventory of cert evidence JSON.")
    ap.add_argument("--router-home", default=_ROUTER_HOME)
    ap.add_argument("--scan-root", action="append", default=None,
                    help="repeatable; defaults to runs + attended_runs")
    ap.add_argument("--out", default=None, help="default: <router-home>/reports/cert_artifact_index.json")
    args = ap.parse_args(argv)

    scan_roots = args.scan_root or list(DEFAULT_SCAN_ROOTS)
    out_path = args.out or os.path.join(args.router_home, "reports", "cert_artifact_index.json")

    index = build_index(router_home=args.router_home, scan_roots=scan_roots)
    _write_json(out_path, index)
    print(json.dumps({k: v for k, v in index.items() if k != "artifacts"}, ensure_ascii=False, indent=2))
    return 0 if index["invalid_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
