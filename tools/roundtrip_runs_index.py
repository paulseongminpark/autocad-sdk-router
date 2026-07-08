#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""roundtrip_runs_index.py -- discoverability index for roundtrip/capstone runs.

Scans a runs root for directories matching glob patterns that directly contain
``summary.json``, extracts traceable metadata (source DWG, sha256, status,
regen batch, verdict totals), and emits a Markdown table plus JSON index so
every numeric claim can be traced back to its run directory.

Stdlib only. Tolerates missing or corrupt JSON (``parse_error`` row, never
crashes).

CLI::

    python tools/roundtrip_runs_index.py --runs-root <dir> \\
        [--pattern e2e_* --pattern capstone_*] \\
        --out-md <path> --out-json <path>
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA = "ariadne.roundtrip_runs_index.v1"
DEFAULT_PATTERNS: Tuple[str, ...] = ("e2e_*", "capstone_*")
VERDICT_TOTAL_KEYS = (
    "regen_attempted_count",
    "diff0_count",
    "modified_count",
    "removed_count",
    "added_count",
)


def _relpath(path: str, base: str) -> str:
    return os.path.relpath(path, base).replace(os.sep, "/")


def _matches_patterns(name: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def discover_run_dirs(runs_root: str, patterns: Sequence[str]) -> List[str]:
    """Immediate child directories matching ``patterns`` with a direct summary.json."""
    if not os.path.isdir(runs_root):
        return []
    found: List[str] = []
    for name in sorted(os.listdir(runs_root)):
        run_dir = os.path.join(runs_root, name)
        if not os.path.isdir(run_dir):
            continue
        if not _matches_patterns(name, patterns):
            continue
        if os.path.isfile(os.path.join(run_dir, "summary.json")):
            found.append(run_dir)
    return found


def _load_json_file(path: str) -> Tuple[Optional[Any], Optional[str]]:
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh), None
    except FileNotFoundError:
        return None, "FileNotFoundError: %s" % path
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, "%s: %s" % (type(exc).__name__, exc)


def _extract_verdict_totals(verdict_data: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(verdict_data, dict):
        return None
    totals = verdict_data.get("totals")
    if not isinstance(totals, dict):
        return None
    out = {key: totals.get(key) for key in VERDICT_TOTAL_KEYS if key in totals}
    return out or None


def index_run_dir(run_dir: str, runs_root: str) -> Dict[str, Any]:
    """Build one index row for a single run directory."""
    record: Dict[str, Any] = {
        "run_dir": _relpath(run_dir, runs_root),
        "source_dwg": None,
        "original_sha256": None,
        "status": None,
        "regen": None,
        "verdict_totals": None,
        "staged_at": None,
        "parse_error": None,
    }

    summary_path = os.path.join(run_dir, "summary.json")
    summary, summary_error = _load_json_file(summary_path)
    if summary_error:
        record["parse_error"] = summary_error
        return record

    staged = (summary or {}).get("staged") or {}
    if isinstance(staged, dict):
        record["source_dwg"] = staged.get("original_path")
        record["original_sha256"] = staged.get("original_sha256")
        record["staged_at"] = staged.get("staged_at")

    if isinstance(summary, dict):
        record["status"] = summary.get("status")
        regen = summary.get("regen")
        if isinstance(regen, dict):
            regen_out = {
                key: regen.get(key)
                for key in ("op_count", "apply_status")
                if key in regen
            }
            record["regen"] = regen_out or None

    verdict_path = os.path.join(run_dir, "verdict.json")
    verdict_data, _verdict_error = _load_json_file(verdict_path)
    record["verdict_totals"] = _extract_verdict_totals(verdict_data)
    return record


def _sort_key(run: Dict[str, Any]) -> Tuple[int, str]:
    staged_at = run.get("staged_at")
    if not staged_at:
        # Group 0 sorts after group 1 when reverse=True (missing staged_at last).
        return (0, "")
    return (1, str(staged_at))


def build_index(runs_root: str, patterns: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Scan ``runs_root`` and return the machine-readable index payload."""
    runs_root = os.path.abspath(runs_root)
    pattern_list = list(patterns if patterns is not None else DEFAULT_PATTERNS)
    runs = [index_run_dir(run_dir, runs_root) for run_dir in discover_run_dirs(runs_root, pattern_list)]
    runs.sort(key=_sort_key, reverse=True)
    return {
        "schema": SCHEMA,
        "generated_from": runs_root,
        "runs": runs,
    }


def _sha16(sha256: Optional[str]) -> str:
    if not sha256:
        return ""
    return str(sha256)[:16]


def _fmt_ops(regen: Optional[Dict[str, Any]]) -> str:
    if not regen:
        return ""
    op_count = regen.get("op_count")
    apply_status = regen.get("apply_status")
    if op_count is not None and apply_status is not None:
        return "%s/%s" % (op_count, apply_status)
    if op_count is not None:
        return str(op_count)
    if apply_status is not None:
        return str(apply_status)
    return ""


def _fmt_diff0_att(totals: Optional[Dict[str, Any]]) -> str:
    if not totals:
        return ""
    diff0 = totals.get("diff0_count")
    attempted = totals.get("regen_attempted_count")
    if diff0 is None and attempted is None:
        return ""
    left = "" if diff0 is None else str(diff0)
    right = "" if attempted is None else str(attempted)
    return "%s/%s" % (left, right)


def _escape_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|")


def render_markdown(index: Dict[str, Any], runs_root: str) -> str:
    """Render the GFM table for ``index['runs']``."""
    _ = runs_root  # kept for symmetry with callers; paths are already relative.
    lines = [
        "| Run | DWG | sha16 | status | ops | diff0/att | timestamp |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for run in index.get("runs") or []:
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s |"
            % (
                _escape_cell(run.get("run_dir")),
                _escape_cell(run.get("source_dwg")),
                _escape_cell(_sha16(run.get("original_sha256"))),
                _escape_cell(run.get("status")),
                _escape_cell(_fmt_ops(run.get("regen"))),
                _escape_cell(_fmt_diff0_att(run.get("verdict_totals"))),
                _escape_cell(run.get("staged_at")),
            )
        )
    return "\n".join(lines) + "\n"


def write_outputs(index: Dict[str, Any], out_md: str, out_json: str, runs_root: str) -> None:
    for path in (out_md, out_json):
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2, default=str)
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(index, runs_root))


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Build a Markdown + JSON index of roundtrip/capstone run directories.",
    )
    ap.add_argument("--runs-root", required=True, help="root directory containing run folders")
    ap.add_argument(
        "--pattern",
        action="append",
        default=None,
        help="glob pattern for run directory names (repeatable; default: e2e_* capstone_*)",
    )
    ap.add_argument("--out-md", required=True, help="output Markdown path")
    ap.add_argument("--out-json", required=True, help="output JSON path")
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    patterns = args.pattern or list(DEFAULT_PATTERNS)
    runs_root = os.path.abspath(args.runs_root)
    index = build_index(runs_root, patterns=patterns)
    write_outputs(index, args.out_md, args.out_json, runs_root)
    print(json.dumps({"schema": index["schema"], "run_count": len(index["runs"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
