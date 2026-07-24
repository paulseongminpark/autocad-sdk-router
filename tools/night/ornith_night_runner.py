#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run an Ornith one-shot queue through the octoloop CLI with resumable receipts."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


DEFAULT_OCTAVIUS = r"D:\dev\99_tools\octoloop"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def fs_safe(value: Any) -> str:
    return "".join(ch if ch.isalnum() or ch in "_.-" else "_" for ch in str(value))


def load_queue(path: str | Path) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8-sig") as fh:
        for line_no, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            obj = json.loads(text)
            if not isinstance(obj, dict) or not obj.get("unit_id"):
                raise ValueError(f"invalid queue item at line {line_no}")
            units.append(obj)
    return units


def read_completed_unit_ids(receipts_path: str | Path) -> set[str]:
    path = Path(receipts_path)
    completed: set[str] = set()
    if not path.exists():
        return completed
    with open(path, "r", encoding="utf-8-sig") as fh:
        for line in fh:
            text = line.strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                continue
            unit_id = obj.get("unit_id") if isinstance(obj, dict) else None
            if unit_id:
                completed.add(str(unit_id))
    return completed


def filter_pending_units(units: Iterable[dict[str, Any]], completed_ids: set[str]) -> list[dict[str, Any]]:
    return [unit for unit in units if str(unit.get("unit_id")) not in completed_ids]


def extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    source = str(text or "")
    for idx, char in enumerate(source):
        if char != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(source[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("no parseable JSON object found")


def _make_packet(unit: dict[str, Any]) -> dict[str, Any]:
    prompt = str(unit.get("prompt") or "")
    unit_id = str(unit["unit_id"])
    return {
        "id": unit_id,
        "type": "packet",
        "kind": "PACKET",
        "producer": "ornith-night-runner",
        "created_at": now_iso(),
        "parent": [],
        "hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "lifecycle": "draft",
        "status": "draft",
        "gates": {"entry": "not_run", "exit": "not_run", "validation": "not_run"},
        "ticket": None,
        "tier": "bulk-local",
        "laneKey": "ornith",
        "mode": "oneshot",
        "prompt": prompt,
        "skill": None,
        "files": [],
        "testCmd": None,
        "contract": {
            "read_allow": [],
            "change_only": [],
            "allow_any_files": True,
            "protected_deny": ["**/.env*", "**/secrets/**", "**/*.lock"],
            "non_goals": [],
            "acceptance": ["one-shot completion text is non-empty"],
            "limits": {"max_files": 0, "max_diff_lines": 0, "repair_iters": 0, "wall_clock_min": 10, "ctx_tokens": 100000},
        },
        "stop_when": ["answer produced", "timeout"],
        "maxTurns": 8,
    }


def _kill_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            check=False,
        )
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def _run_process(argv: list[str], cwd: Path, timeout_s: float) -> tuple[int | None, str, str, bool]:
    proc = subprocess.Popen(
        argv,
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        return proc.returncode, stdout, stderr, False
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc.pid)
        stdout, stderr = proc.communicate()
        return None, stdout, stderr, True


def _receipt_path_from_cli_json(cli_obj: dict[str, Any]) -> Path | None:
    run_dir = cli_obj.get("runDir")
    receipt_id = cli_obj.get("receipt")
    if not run_dir or not receipt_id:
        return None
    return Path(str(run_dir)) / "receipts" / f"{fs_safe(receipt_id)}.json"


def extract_completion_text(stdout: str, stderr: str = "") -> str:
    try:
        cli_obj = extract_json_object(stdout)
    except ValueError:
        cli_obj = {}
    if cli_obj:
        receipt_path = _receipt_path_from_cli_json(cli_obj)
        if receipt_path is not None:
            candidates = [receipt_path]
            if not receipt_path.exists() and receipt_path.parent.exists():
                candidates.extend(sorted(receipt_path.parent.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True))
            for path in candidates:
                try:
                    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
                except Exception:
                    continue
                text = receipt.get("result_text")
                if text:
                    return str(text).strip()
        for key in ("result_text", "finalText", "result", "completion", "text"):
            value = cli_obj.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    fallback = stdout.strip()
    if fallback:
        return fallback
    return stderr.strip()


@dataclass
class UnitResult:
    unit_id: str
    ok: bool
    elapsed_s: float
    raw_text: str = ""
    parsed: dict[str, Any] | None = None
    chars: int = 0
    error_class: str | None = None
    stderr: str = ""


def run_unit(unit: dict[str, Any], octavius_root: str | Path, repo: str | Path, per_call_timeout: float) -> UnitResult:
    unit_id = str(unit["unit_id"])
    octo = Path(octavius_root)
    started = time.monotonic()
    fd = -1
    packet_path: str | None = None
    try:
        fd, packet_path = tempfile.mkstemp(prefix=f"{fs_safe(unit_id)}-", suffix=".packet.json")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fd = -1
            json.dump(_make_packet(unit), fh, ensure_ascii=False, sort_keys=True)
        argv = [
            "node",
            str(octo / "bin" / "octavius.mjs"),
            "run",
            "--repo",
            str(Path(repo).resolve()),
            "--packet",
            packet_path,
        ]
        _returncode, stdout, stderr, timed_out = _run_process(argv, octo, per_call_timeout)
        elapsed = time.monotonic() - started
        if timed_out:
            return UnitResult(unit_id=unit_id, ok=False, elapsed_s=elapsed, error_class="timeout", stderr=stderr)
        raw_text = extract_completion_text(stdout, stderr)
        if not raw_text.strip():
            return UnitResult(unit_id=unit_id, ok=False, elapsed_s=elapsed, error_class="empty", stderr=stderr)
        parsed = None
        if unit.get("kind") == "def_annotation":
            try:
                parsed = extract_json_object(raw_text)
            except ValueError:
                return UnitResult(unit_id=unit_id, ok=False, elapsed_s=elapsed, raw_text=raw_text, error_class="parse", stderr=stderr)
        return UnitResult(
            unit_id=unit_id,
            ok=True,
            elapsed_s=elapsed,
            raw_text=raw_text,
            parsed=parsed,
            chars=len(raw_text),
            stderr=stderr,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        elapsed = time.monotonic() - started
        return UnitResult(unit_id=unit_id, ok=False, elapsed_s=elapsed, error_class="spawn", stderr=str(exc))
    finally:
        if fd != -1:
            os.close(fd)
        if packet_path:
            try:
                os.unlink(packet_path)
            except OSError:
                pass


class JsonlChainWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = self._seed_hash()
        self._fh = open(self.path, "a", encoding="utf-8", buffering=1, newline="\n")

    def _seed_hash(self) -> str | None:
        if not self.path.exists():
            return None
        lines = [line.rstrip("\n") for line in self.path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        if not lines:
            return None
        return hashlib.sha256(lines[-1].encode("utf-8")).hexdigest()

    def write(self, obj: dict[str, Any]) -> None:
        record = dict(obj)
        record.setdefault("prev_hash", self._last_hash)
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        self._fh.write(line + "\n")
        self._fh.flush()
        self._last_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "JsonlChainWriter":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.close()


def append_claim(out_dir: str | Path, result: UnitResult, kind: str | None) -> None:
    claims = Path(out_dir) / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    path = claims / f"{fs_safe(result.unit_id)}.json"
    payload = {
        "unit_id": result.unit_id,
        "kind": kind,
        "parsed": result.parsed,
        "raw_text": result.raw_text,
        "ts": now_iso(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def parse_deadline(value: str, now: datetime | None = None) -> datetime:
    base = now or datetime.now().astimezone()
    hour_text, minute_text = value.split(":", 1)
    deadline = base.replace(hour=int(hour_text), minute=int(minute_text), second=0, microsecond=0)
    if deadline <= base:
        deadline += timedelta(days=1)
    return deadline


def _log(log_fh: Any, message: str) -> None:
    log_fh.write(f"{now_iso()} {message}\n")
    log_fh.flush()


def run_queue(args: argparse.Namespace) -> str:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    receipts_path = out_dir / "receipts.jsonl"
    log_path = out_dir / "runner.log"
    units = load_queue(args.queue)
    completed = read_completed_unit_ids(receipts_path)
    pending = filter_pending_units(units, completed)
    concurrency = max(1, min(int(args.concurrency), 32))
    deadline = parse_deadline(args.deadline)
    repo = Path.cwd()
    done = 0
    failed = 0
    processed = 0
    consecutive_failures = 0
    last_stderr = ""
    terminal_state: str | None = None

    with open(log_path, "a", encoding="utf-8", buffering=1, newline="\n") as log_fh, JsonlChainWriter(receipts_path) as receipts:
        _log(log_fh, f"loaded={len(units)} skipped={len(completed)} pending={len(pending)} concurrency={concurrency} deadline={deadline.isoformat()}")
        next_idx = 0
        active: dict[concurrent.futures.Future[UnitResult], dict[str, Any]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            while active or next_idx < len(pending):
                now = datetime.now().astimezone()
                while (
                    len(active) < concurrency
                    and next_idx < len(pending)
                    and consecutive_failures < args.max_consecutive_failures
                    and now < deadline
                ):
                    unit = pending[next_idx]
                    next_idx += 1
                    remaining = max(1.0, (deadline - now).total_seconds())
                    timeout = min(float(args.per_call_timeout), remaining)
                    _log(log_fh, f"start unit_id={unit.get('unit_id')} timeout_s={timeout:.1f}")
                    fut = pool.submit(run_unit, unit, args.octavius, repo, timeout)
                    active[fut] = unit
                    now = datetime.now().astimezone()

                if not active:
                    if next_idx >= len(pending):
                        terminal_state = "exhausted"
                    elif consecutive_failures >= args.max_consecutive_failures:
                        terminal_state = "breaker"
                    else:
                        terminal_state = "deadline"
                    break

                finished, _unfinished = concurrent.futures.wait(active, timeout=1.0, return_when=concurrent.futures.FIRST_COMPLETED)
                if not finished:
                    if datetime.now().astimezone() >= deadline and next_idx < len(pending):
                        terminal_state = "deadline"
                    continue

                for fut in finished:
                    unit = active.pop(fut)
                    result = fut.result()
                    processed += 1
                    if result.ok:
                        done += 1
                        consecutive_failures = 0
                        append_claim(out_dir, result, unit.get("kind"))
                        receipts.write({
                            "unit_id": result.unit_id,
                            "ok": True,
                            "elapsed_s": round(result.elapsed_s, 3),
                            "ts": now_iso(),
                            "chars": result.chars,
                        })
                        _log(log_fh, f"ok unit_id={result.unit_id} elapsed_s={result.elapsed_s:.3f} chars={result.chars}")
                    else:
                        failed += 1
                        consecutive_failures += 1
                        last_stderr = result.stderr
                        receipts.write({
                            "unit_id": result.unit_id,
                            "ok": False,
                            "error_class": result.error_class or "spawn",
                            "ts": now_iso(),
                        })
                        _log(log_fh, f"fail unit_id={result.unit_id} class={result.error_class} consecutive={consecutive_failures}")
                    if processed % 25 == 0:
                        receipts.write({"heartbeat": True, "done": done, "failed": failed, "ts": now_iso()})
                    if consecutive_failures >= args.max_consecutive_failures:
                        terminal_state = "breaker"

                if terminal_state == "breaker":
                    break

            if terminal_state == "breaker":
                for fut in active:
                    fut.cancel()

        if terminal_state is None:
            if consecutive_failures >= args.max_consecutive_failures:
                terminal_state = "breaker"
            elif datetime.now().astimezone() >= deadline and next_idx < len(pending):
                terminal_state = "deadline"
            else:
                terminal_state = "exhausted"
        if terminal_state == "breaker":
            (out_dir / "BREAKER_TRIPPED.txt").write_text(last_stderr or "max consecutive failures reached", encoding="utf-8")
        receipts.write({"terminal": True, "state": terminal_state, "done": done, "failed": failed})
        _log(log_fh, f"terminal state={terminal_state} done={done} failed={failed}")
    return terminal_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--per-call-timeout", type=float, default=240)
    parser.add_argument("--max-consecutive-failures", type=int, default=5)
    parser.add_argument("--deadline", default="07:00")
    parser.add_argument("--octavius", default=DEFAULT_OCTAVIUS)
    args = parser.parse_args(argv)
    state = run_queue(args)
    return 0 if state in {"exhausted", "deadline", "breaker"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
