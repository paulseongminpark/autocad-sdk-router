#!/usr/bin/env python
"""Build a corpus_query-compatible JSONL ledger from a corpus-batch run directory.

WHY: tools/corpus_query.py consumes one JSON object per corpus file --
source_path/status/error_class/reason plus an entity-count breakdown
(entity_count, by_layer, by_entity_type) that summarize()/anomalies() fold
into aggregates and z-score outliers. The entity-type/layer histograms are
counted from the op_02 "inspect entities" result's ``entities`` list, which
the router truncates past a size cap (``truncated: true``). Emitting
by_layer/by_entity_type from a truncated list would silently produce a
partial histogram that corpus_query would treat as the whole file's
population -- so this builder omits both fields whenever
``entities_truncated`` is not exactly ``False``, rather than emit a
misleading partial count.

Generalizes an ad-hoc one-off script (build_ledger.py, run-specific,
hardcoded RUN_DIR) into a reusable CLI:

    python tools/corpus_ledger.py --run-dir <dir> [--out <path>]

Each corpus file is expected to live under ``<run-dir>/0*/`` with a
``result_envelope.json`` (the per-file batch-run envelope) and per-op
subdirectories named ``op_NN_<name>/stdout.txt`` holding the worker's JSON
stdout payload.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _read_text_best_effort(path: Path) -> str:
    """Read op stdout as utf-8, falling back to cp949, then replace-mode utf-8.

    Worker stdout is produced by native/CLI tooling on a cp949-locale
    Windows box; some payloads are utf-8, some are cp949-encoded Korean
    text. Never raise on decode -- a corpus file's row must still be built
    even if its op stdout is undecodable, so the last resort replaces
    unmappable bytes instead of failing.
    """
    for enc in ("utf-8", "cp949"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _read_json_payload(path: Path) -> dict[str, Any] | None:
    """Extract the first JSON object embedded in a worker stdout file.

    Worker stdout may carry log lines before the JSON payload; find the
    first '{' and parse from there.
    """
    text = _read_text_best_effort(path)
    i = text.find("{")
    if i < 0:
        return None
    return json.loads(text[i:])


def _op_result(env: dict[str, Any], file_dir: Path, op_dirname: str,
               operation_id: str) -> dict[str, Any] | None:
    """Return one op's native result payload, or None.

    Source preference matters for correctness, not just convenience: the op's
    ``result_ref`` JSON (written by the native job with utf-8-sig) preserves
    Korean layer names exactly, while ``stdout.txt`` passes through a
    cp949-locale console pipeline that can bake U+FFFD replacement characters
    into non-ASCII text (wave-7 shard audit: every checked result_ref was
    clean where the matching stdout was corrupted). stdout.txt is only a
    fallback for runs whose result_ref artifacts were pruned.
    """
    for op in env.get("ops_run") or []:
        if op.get("operation") != operation_id:
            continue
        ref = op.get("result_ref")
        if not ref:
            break
        ref_path = Path(ref)
        if not ref_path.exists():
            break
        try:
            doc = json.loads(ref_path.read_text(encoding="utf-8-sig"))
        except Exception:
            break
        result = doc.get("result")
        if isinstance(result, dict):
            return result
        break

    stdout_path = file_dir / op_dirname / "stdout.txt"
    if not stdout_path.exists():
        return None
    try:
        doc = _read_json_payload(stdout_path)
    except Exception:
        return None
    if not doc:
        return None
    execution = doc.get("execution", {}) or {}
    engine_output = execution.get("engine_output", {}) or {}
    result = engine_output.get("result", {}) or {}
    return result.get("result")


def build_ledger(run_dir: Path) -> list[dict[str, Any]]:
    """Build the in-memory ledger rows for every corpus file under run_dir.

    Pure function: no file writes, no printing. Callers (main() here, or
    tests) own I/O. One row per ``0*/result_envelope.json`` match, sorted
    by path for deterministic ordering.
    """
    run_dir = Path(run_dir)
    rows: list[dict[str, Any]] = []
    envelope_paths = sorted(run_dir.glob("0*/result_envelope.json"))
    for envelope_path in envelope_paths:
        env = json.loads(envelope_path.read_text(encoding="utf-8-sig"))
        file_dir = envelope_path.parent

        row: dict[str, Any] = {
            "source_path": env.get("source_path"),
            "ordinal": env.get("ordinal"),
            "status": env.get("status"),
            "error_class": env.get("error_class"),
            "reason": env.get("reason"),
            "source_sha256_match": env.get("source_sha256_match"),
            "worker_exit_code": env.get("worker_exit_code"),
        }

        summary = _op_result(env, file_dir, "op_00_inspect_database_summary",
                             "inspect.database.summary")
        if summary:
            row["entity_count"] = summary.get("modelspace_entities")
            for key in ("layers", "blocks", "layouts", "insunits"):
                row[key] = summary.get(key)

        entities = _op_result(env, file_dir, "op_02_inspect_entities",
                              "inspect.entities")
        if entities:
            row["entities_truncated"] = entities.get("truncated")
            row["matching_entities"] = entities.get("matching_entities")
            records = entities.get("entities") or []
            if entities.get("truncated") is False and records:
                row["by_entity_type"] = dict(Counter(r.get("dxf_name") for r in records))
                row["by_layer"] = dict(Counter(r.get("layer") for r in records))

        ops_run = env.get("ops_run") or []
        row["op_elapsed_sec"] = {o.get("operation"): o.get("elapsed_sec") for o in ops_run}
        row["op_status"] = {o.get("operation"): o.get("status") for o in ops_run}

        rows.append(row)

    return rows


def _summary(rows: list[dict[str, Any]], out_path: Path) -> dict[str, Any]:
    n_ok = sum(1 for r in rows if r.get("status") == "ok")
    n_sha = sum(1 for r in rows if r.get("source_sha256_match"))
    n_trunc = sum(1 for r in rows if r.get("entities_truncated"))
    total_entities = sum(int(r.get("entity_count") or 0) for r in rows)
    op_bad = [
        (r.get("ordinal"), op, status)
        for r in rows
        for op, status in (r.get("op_status") or {}).items()
        if status != "ok"
    ]
    return {
        "rows": len(rows),
        "ok": n_ok,
        "sha_match": n_sha,
        "entities_total": total_entities,
        "truncated_lists": n_trunc,
        "non_ok_ops": op_bad[:20],
        "non_ok_op_count": len(op_bad),
        "out": str(out_path),
    }


def _write_jsonl(rows: list[dict[str, Any]], out_path: Path) -> None:
    with open(out_path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a corpus_query-compatible JSONL ledger from a corpus-batch run directory"
    )
    parser.add_argument("--run-dir", required=True, help="corpus-batch run directory")
    parser.add_argument(
        "--out",
        default=None,
        help="output JSONL path (default: <run-dir>/ledger.jsonl)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    out_path = Path(args.out) if args.out else run_dir / "ledger.jsonl"

    rows = build_ledger(run_dir)
    _write_jsonl(rows, out_path)

    print(json.dumps(_summary(rows, out_path), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
