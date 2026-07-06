#!/usr/bin/env python
from __future__ import annotations

import argparse
import dataclasses
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"
RESULT_FILE = "result_envelope.json"
SUMMARY_JSON = "summary.json"
SUMMARY_MD = "summary.md"
WORKER_REQUEST = "worker_request.json"
DEFAULT_TIMEOUT_SEC = 240
RESULT_SCHEMA = "ariadne.corpus_batch.result.v1"
SUMMARY_SCHEMA = "ariadne.corpus_batch.summary.v1"
DEFAULT_OPS = [
    {"id": "inspect.database.summary", "args": {}},
    {"id": "inspect.layers", "args": {}},
    {"id": "inspect.entities", "args": {}},
]
TERMINAL_STATUSES = {"ok", "failed", "timeout"}


@dataclasses.dataclass(frozen=True)
class CorpusEntry:
    ordinal: int
    source_path: str
    expected_sha256: str | None
    input_kind: str

    def to_json(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "CorpusEntry":
        return cls(
            ordinal=int(payload["ordinal"]),
            source_path=str(payload["source_path"]),
            expected_sha256=(str(payload["expected_sha256"]) if payload.get("expected_sha256") else None),
            input_kind=str(payload["input_kind"]),
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_name(value: str) -> str:
    cooked = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value.strip())
    cooked = cooked.strip("._")
    return cooked or "unnamed"


def _json_dump(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_manifest_path(raw_path: str, manifest_path: Path) -> str:
    path = Path(raw_path)
    if not path.is_absolute():
        manifest_relative = (manifest_path.parent / path).resolve()
        repo_relative = (ROOT / path).resolve()
        if manifest_relative.exists() or not repo_relative.exists():
            path = manifest_relative
        else:
            path = repo_relative
    return str(path)


def load_manifest_entries(manifest_path: str | Path) -> list[CorpusEntry]:
    manifest_path = Path(manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("manifest must be a JSON list of {path, sha256?} objects")
    entries: list[CorpusEntry] = []
    for ordinal, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"manifest row {ordinal} must be an object")
        raw_path = row.get("path")
        if not raw_path:
            raise ValueError(f"manifest row {ordinal} missing required field 'path'")
        entries.append(
            CorpusEntry(
                ordinal=ordinal,
                source_path=_resolve_manifest_path(str(raw_path), manifest_path),
                expected_sha256=(str(row["sha256"]).lower() if row.get("sha256") else None),
                input_kind="manifest",
            )
        )
    return entries


def expand_glob_entries(pattern: str) -> list[CorpusEntry]:
    matches = [
        Path(p).resolve()
        for p in glob.glob(pattern, recursive=True)
        if Path(p).is_file()
    ]
    ordered = sorted(matches, key=lambda p: str(p).lower())
    return [
        CorpusEntry(
            ordinal=ordinal,
            source_path=str(path),
            expected_sha256=None,
            input_kind="glob",
        )
        for ordinal, path in enumerate(ordered)
    ]


def parse_ops(ops_text: str | None = None, ops_file: str | None = None) -> list[dict[str, Any]]:
    if ops_text and ops_file:
        raise ValueError("use either --ops or --ops-file, not both")
    if ops_file:
        raw = json.loads(Path(ops_file).read_text(encoding="utf-8"))
        if not isinstance(raw, list) or not raw:
            raise ValueError("ops file must be a non-empty JSON list")
        ops: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, str):
                ops.append({"id": item, "args": {}})
                continue
            if not isinstance(item, dict) or not item.get("id"):
                raise ValueError("ops file rows must be strings or {id, args?} objects")
            ops.append({"id": str(item["id"]), "args": dict(item.get("args") or {})})
        return ops
    if ops_text:
        ops = [{"id": chunk.strip(), "args": {}} for chunk in ops_text.split(",") if chunk.strip()]
        if not ops:
            raise ValueError("--ops produced no operation ids")
        return ops
    return [dict(op) for op in DEFAULT_OPS]


def should_resume_skip(result_path: str | Path, *, force: bool) -> bool:
    if force:
        return False
    result_path = Path(result_path)
    if not result_path.is_file():
        return False
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return payload.get("status") in TERMINAL_STATUSES


def classify_error(*, source_path: str, status: str, reason: str | None) -> str:
    if Path(source_path).suffix.lower() != ".dwg":
        return "non-dwg"
    text = (reason or "").lower()
    if status == "timeout" or "timed out" in text or "timeout" in text:
        return "timeout"
    if "password" in text or "encrypted" in text or "proxy" in text:
        return "password_or_proxy"
    unreadable_needles = (
        "not found",
        "permission denied",
        "access is denied",
        "read_dwg_failed",
        "failed to read",
        "unreadable",
        "sha256 mismatch",
    )
    if any(needle in text for needle in unreadable_needles):
        return "unreadable"
    return "extraction-crash"


def build_summary(results: list[dict[str, Any]], *, started_at: str, finished_at: str) -> dict[str, Any]:
    status_counts = Counter(str(result.get("status") or "failed") for result in results)
    error_counts = Counter(
        str(result["error_class"])
        for result in results
        if result.get("error_class")
    )
    total_elapsed = sum(
        float((result.get("timings") or {}).get("elapsed_sec") or 0.0)
        for result in results
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "started_at": started_at,
        "finished_at": finished_at,
        "total_inputs": len(results),
        "counts_by_status": dict(sorted(status_counts.items())),
        "counts_by_error_class": dict(sorted(error_counts.items())),
        "total_elapsed_sec": round(total_elapsed, 3),
    }


def _result_envelope(
    *,
    entry: CorpusEntry,
    run_dir: Path,
    status: str,
    error_class: str | None,
    source_sha256: str | None,
    staged_path: str | None,
    ops_run: list[dict[str, Any]],
    started_at: str,
    finished_at: str,
    elapsed_sec: float,
    reason: str | None = None,
    worker_exit_code: int | None = None,
    source_sha256_expected: str | None = None,
    source_sha256_match: bool | None = None,
) -> dict[str, Any]:
    payload = {
        "schema": RESULT_SCHEMA,
        "ordinal": entry.ordinal,
        "source_path": entry.source_path,
        "source_sha256": source_sha256,
        "source_sha256_expected": source_sha256_expected,
        "source_sha256_match": source_sha256_match,
        "staged_path": staged_path,
        "ops_run": ops_run,
        "status": status,
        "error_class": error_class,
        "run_dir": str(run_dir),
        "timings": {
            "started_at": started_at,
            "finished_at": finished_at,
            "elapsed_sec": round(elapsed_sec, 3),
        },
    }
    if reason:
        payload["reason"] = reason
    if worker_exit_code is not None:
        payload["worker_exit_code"] = worker_exit_code
    return payload


def _operation_record(op: dict[str, Any], result: dict[str, Any], elapsed_sec: float) -> dict[str, Any]:
    op_status = str(result.get("status") or "error")
    reason = result.get("reason")
    op_error_class = None if op_status == "ok" else classify_error(
        source_path=str(result.get("staged_copy") or result.get("staged_result") or "input.dwg"),
        status="timeout" if op_status == "timeout" else "failed",
        reason=str(reason or (result.get("result") or {}).get("error") or ""),
    )
    return {
        "operation": str(op["id"]),
        "args": dict(op.get("args") or {}),
        "status": op_status,
        "error_class": op_error_class,
        "reason": reason,
        "elapsed_sec": round(elapsed_sec, 3),
        "result_ref": result.get("result_ref"),
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
    }


def _kill_process_tree(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
                text=True,
            )
        except Exception:
            pass
    else:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=30)
    except Exception:
        pass


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _worker_impl(request_path: Path) -> int:
    if str(ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(ROOT / "tools"))
    import cadctl  # noqa: E402

    request = _load_json(request_path)
    entry = CorpusEntry.from_json(request["entry"])
    run_dir = Path(request["run_dir"])
    ops = list(request["ops"])
    started_at = _now_iso()
    started_monotonic = time.monotonic()
    result_path = run_dir / RESULT_FILE
    staged_path = run_dir / "source_staged.dwg"
    source = Path(entry.source_path)
    ops_run: list[dict[str, Any]] = []
    source_sha = None
    sha_match = None
    def persist_progress(status: str, *, error_class: str | None = None, reason: str | None = None) -> None:
        payload = _result_envelope(
            entry=entry,
            run_dir=run_dir,
            status=status,
            error_class=error_class,
            source_sha256=source_sha,
            staged_path=str(staged_path) if staged_path.exists() else None,
            ops_run=ops_run,
            started_at=started_at,
            finished_at=_now_iso(),
            elapsed_sec=time.monotonic() - started_monotonic,
            reason=reason,
            source_sha256_expected=entry.expected_sha256,
            source_sha256_match=sha_match,
        )
        _json_dump(payload, result_path)
    try:
        if source.suffix.lower() != ".dwg":
            payload = _result_envelope(
                entry=entry,
                run_dir=run_dir,
                status="failed",
                error_class="non-dwg",
                source_sha256=None,
                staged_path=None,
                ops_run=[],
                started_at=started_at,
                finished_at=_now_iso(),
                elapsed_sec=time.monotonic() - started_monotonic,
                reason=f"input is not a .dwg file: {source}",
                source_sha256_expected=entry.expected_sha256,
                source_sha256_match=None,
            )
            _json_dump(payload, result_path)
            return 0

        source_sha = _sha256_file(source)
        if entry.expected_sha256:
            sha_match = source_sha.lower() == entry.expected_sha256.lower()
            if not sha_match:
                payload = _result_envelope(
                    entry=entry,
                    run_dir=run_dir,
                    status="failed",
                    error_class="unreadable",
                    source_sha256=source_sha,
                    staged_path=None,
                    ops_run=[],
                    started_at=started_at,
                    finished_at=_now_iso(),
                    elapsed_sec=time.monotonic() - started_monotonic,
                    reason=f"sha256 mismatch for source drawing: expected {entry.expected_sha256}, got {source_sha}",
                    source_sha256_expected=entry.expected_sha256,
                    source_sha256_match=False,
                )
                _json_dump(payload, result_path)
                return 0

        shutil.copy2(source, staged_path)
        try:
            os.chmod(staged_path, 0o666)
        except OSError:
            pass
        persist_progress("running")

        cad = cadctl.Cad(router_home=ROOT)
        overall_status = "ok"
        overall_error_class = None
        overall_reason = None
        for ordinal, op in enumerate(ops):
            op_dir = run_dir / f"op_{ordinal:02d}_{_safe_name(str(op['id']))}"
            op_dir.mkdir(parents=True, exist_ok=True)
            op_started = time.monotonic()
            result = cad.run_operation(
                str(op["id"]),
                args=dict(op.get("args") or {}),
                dwg_path=str(staged_path),
                out_dir=str(op_dir),
            )
            op_elapsed = time.monotonic() - op_started
            op_record = _operation_record(op, result, op_elapsed)
            ops_run.append(op_record)
            if op_record["status"] != "ok" and overall_status == "ok":
                overall_status = "failed"
                overall_error_class = op_record["error_class"]
                overall_reason = op_record["reason"] or f"operation failed: {op['id']}"
            persist_progress(
                "running" if ordinal < len(ops) - 1 else overall_status,
                error_class=overall_error_class,
                reason=overall_reason,
            )

        payload = _result_envelope(
            entry=entry,
            run_dir=run_dir,
            status=overall_status,
            error_class=overall_error_class,
            source_sha256=source_sha,
            staged_path=str(staged_path),
            ops_run=ops_run,
            started_at=started_at,
            finished_at=_now_iso(),
            elapsed_sec=time.monotonic() - started_monotonic,
            reason=overall_reason,
            source_sha256_expected=entry.expected_sha256,
            source_sha256_match=sha_match,
        )
        _json_dump(payload, result_path)
        return 0
    except Exception as exc:
        payload = _result_envelope(
            entry=entry,
            run_dir=run_dir,
            status="failed",
            error_class=classify_error(source_path=entry.source_path, status="failed", reason=str(exc)),
            source_sha256=source_sha,
            staged_path=str(staged_path) if staged_path.exists() else None,
            ops_run=ops_run,
            started_at=started_at,
            finished_at=_now_iso(),
            elapsed_sec=time.monotonic() - started_monotonic,
            reason=f"{type(exc).__name__}: {exc}",
            source_sha256_expected=entry.expected_sha256,
            source_sha256_match=sha_match,
        )
        _json_dump(payload, result_path)
        return 1


def _run_entry_parent(entry: CorpusEntry, *, ops: list[dict[str, Any]], run_dir: Path, timeout_sec: int) -> dict[str, Any]:
    request_path = run_dir / WORKER_REQUEST
    result_path = run_dir / RESULT_FILE
    stdout_path = run_dir / "worker_stdout.txt"
    stderr_path = run_dir / "worker_stderr.txt"
    _json_dump(
        {
            "entry": entry.to_json(),
            "run_dir": str(run_dir),
            "ops": ops,
            "timeout_sec": timeout_sec,
        },
        request_path,
    )
    cmd = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--worker-request", str(request_path)]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    started_at = _now_iso()
    started_monotonic = time.monotonic()
    with stdout_path.open("w", encoding="utf-8", newline="") as out_fh, stderr_path.open("w", encoding="utf-8", newline="") as err_fh:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=out_fh,
            stderr=err_fh,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        timed_out = False
        deadline = time.monotonic() + timeout_sec
        while True:
            if proc.poll() is not None:
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(0.5)
        exit_code = proc.poll()
    if timed_out:
        _kill_process_tree(proc)
        partial_ops: list[dict[str, Any]] = []
        partial_source_sha = None
        partial_staged_path = str(run_dir / "source_staged.dwg") if (run_dir / "source_staged.dwg").exists() else None
        partial_expected = entry.expected_sha256
        partial_match = None
        if result_path.is_file():
            try:
                partial = _load_json(result_path)
                partial_ops = list(partial.get("ops_run") or [])
                partial_source_sha = partial.get("source_sha256")
                partial_staged_path = partial.get("staged_path") or partial_staged_path
                partial_expected = partial.get("source_sha256_expected")
                partial_match = partial.get("source_sha256_match")
            except Exception:
                pass
        return _result_envelope(
            entry=entry,
            run_dir=run_dir,
            status="timeout",
            error_class="timeout",
            source_sha256=partial_source_sha,
            staged_path=partial_staged_path,
            ops_run=partial_ops,
            started_at=started_at,
            finished_at=_now_iso(),
            elapsed_sec=time.monotonic() - started_monotonic,
            reason=f"worker timed out after {timeout_sec}s; process tree was killed",
            worker_exit_code=proc.poll(),
            source_sha256_expected=partial_expected,
            source_sha256_match=partial_match,
        )
    if result_path.is_file():
        payload = _load_json(result_path)
        payload["worker_exit_code"] = exit_code
        return payload
    reason = f"worker exited {exit_code} without writing {RESULT_FILE}"
    return _result_envelope(
        entry=entry,
        run_dir=run_dir,
        status="failed",
        error_class="extraction-crash",
        source_sha256=None,
        staged_path=None,
        ops_run=[],
        started_at=started_at,
        finished_at=_now_iso(),
        elapsed_sec=time.monotonic() - started_monotonic,
        reason=reason,
        worker_exit_code=exit_code,
        source_sha256_expected=entry.expected_sha256,
        source_sha256_match=None,
    )


def _summary_lines(summary: dict[str, Any]) -> list[str]:
    status_bits = ", ".join(f"{key}={value}" for key, value in sorted((summary.get("counts_by_status") or {}).items()))
    error_bits = ", ".join(f"{key}={value}" for key, value in sorted((summary.get("counts_by_error_class") or {}).items()))
    lines = [
        f"run_dir: {summary.get('run_dir')}",
        f"total_inputs: {summary.get('total_inputs')}",
        f"counts_by_status: {status_bits or 'none'}",
        f"counts_by_error_class: {error_bits or 'none'}",
        f"total_elapsed_sec: {summary.get('total_elapsed_sec')}",
    ]
    return lines


def _write_summary_md(summary: dict[str, Any], results: list[dict[str, Any]], out_dir: Path) -> None:
    lines = [
        "# Corpus Batch Summary",
        "",
        *[f"- {line}" for line in _summary_lines(summary)],
        "",
        "| idx | status | error_class | elapsed_sec | source |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for result in results:
        lines.append(
            "| {idx} | {status} | {error_class} | {elapsed} | `{source}` |".format(
                idx=result.get("ordinal"),
                status=result.get("status"),
                error_class=result.get("error_class") or "",
                elapsed=(result.get("timings") or {}).get("elapsed_sec"),
                source=result.get("source_path"),
            )
        )
    (out_dir / SUMMARY_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_batch(
    *,
    manifest_path: str | None,
    glob_pattern: str | None,
    out_dir: str | None,
    force: bool,
    timeout_sec: int,
    ops: list[dict[str, Any]],
) -> dict[str, Any]:
    if bool(manifest_path) == bool(glob_pattern):
        raise ValueError("provide exactly one of --manifest or --glob")
    entries = load_manifest_entries(manifest_path) if manifest_path else expand_glob_entries(str(glob_pattern))
    if not entries:
        raise ValueError("no input files matched")
    run_dir = Path(out_dir) if out_dir else (RUNS_DIR / f"corpus_batch_{_stamp()}")
    run_dir.mkdir(parents=True, exist_ok=True)
    started_at = _now_iso()
    results: list[dict[str, Any]] = []
    for entry in entries:
        source_name = _safe_name(Path(entry.source_path).stem)
        case_dir = run_dir / f"{entry.ordinal:04d}_{source_name}"
        if force and case_dir.exists():
            shutil.rmtree(case_dir)
        case_dir.mkdir(parents=True, exist_ok=True)
        result_path = case_dir / RESULT_FILE
        if should_resume_skip(result_path, force=force):
            payload = _load_json(result_path)
            payload["resumed"] = True
            results.append(payload)
            continue
        payload = _run_entry_parent(entry, ops=ops, run_dir=case_dir, timeout_sec=timeout_sec)
        _json_dump(payload, result_path)
        results.append(payload)
    finished_at = _now_iso()
    summary = build_summary(results, started_at=started_at, finished_at=finished_at)
    summary.update(
        {
            "run_dir": str(run_dir),
            "manifest_path": manifest_path,
            "glob_pattern": glob_pattern,
            "ops": ops,
            "result_files": [str(run_dir / f"{entry.ordinal:04d}_{_safe_name(Path(entry.source_path).stem)}" / RESULT_FILE) for entry in entries],
        }
    )
    _json_dump(summary, run_dir / SUMMARY_JSON)
    _write_summary_md(summary, results, run_dir)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a multi-DWG corpus batch through cadctl with per-file isolation")
    parser.add_argument("--manifest", help="JSON list of {path, sha256?} rows")
    parser.add_argument("--glob", dest="glob_pattern", help="filesystem glob for DWG inputs")
    parser.add_argument("--out-dir", help="existing or new run directory (default: runs/corpus_batch_<stamp>)")
    parser.add_argument("--force", action="store_true", help="re-run files even when a result envelope already exists")
    parser.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC, help="per-file worker timeout in seconds")
    parser.add_argument("--ops", help="comma-separated operation ids")
    parser.add_argument("--ops-file", help="JSON file containing a list of op ids or {id,args} rows")
    parser.add_argument("--worker-request", help=argparse.SUPPRESS)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.worker_request:
        return _worker_impl(Path(args.worker_request))
    try:
        ops = parse_ops(args.ops, args.ops_file)
        summary = run_batch(
            manifest_path=args.manifest,
            glob_pattern=args.glob_pattern,
            out_dir=args.out_dir,
            force=bool(args.force),
            timeout_sec=int(args.timeout_sec),
            ops=ops,
        )
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print("\n".join(_summary_lines(summary)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
