#!/usr/bin/env python
"""Analysis/query layer over a completed corpus-batch JSONL ledger.

Each ledger line is a JSON object describing one corpus file, following the
field names used by ``tools/corpus_batch.py``'s per-file result envelope
(``source_path``, ``status``, ``error_class``, ``reason``) plus the
entity-count breakdown a ledger-building step computes from that file's
``inspect.layers`` / ``inspect.entities`` op results (``entity_count``,
``by_layer``, ``by_entity_type``).
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

OK_STATUS = "ok"


def _row_file(row: dict[str, Any]) -> Any:
    return row.get("source_path") or row.get("file")


def load_ledger(jsonl_path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    malformed = 0
    with open(jsonl_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(row, dict):
                malformed += 1
                continue
            rows.append(row)
    if malformed:
        logger.warning("skipped %d malformed ledger line(s) in %s", malformed, jsonl_path)
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    files = len(rows)
    ok = sum(1 for row in rows if row.get("status") == OK_STATUS)
    failed = files - ok
    total_entities = sum(int(row.get("entity_count") or 0) for row in rows)

    by_layer: Counter[str] = Counter()
    by_entity_type: Counter[str] = Counter()
    for row in rows:
        by_layer.update(row.get("by_layer") or {})
        by_entity_type.update(row.get("by_entity_type") or {})

    return {
        "files": files,
        "ok": ok,
        "failed": failed,
        "total_entities": total_entities,
        "by_layer": dict(by_layer),
        "by_entity_type": dict(by_entity_type),
    }


def anomalies(rows: list[dict[str, Any]], entity_z: float = 3.0) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    for row in rows:
        if row.get("status") != OK_STATUS:
            reason = row.get("reason") or row.get("error_class") or "extraction failed"
            findings.append({"file": _row_file(row), "reason": str(reason)})

    counted = [
        (_row_file(row), float(row["entity_count"]))
        for row in rows
        if row.get("status") == OK_STATUS and row.get("entity_count") is not None
    ]
    if len(counted) >= 3:
        values = [value for _, value in counted]
        mean = statistics.fmean(values)
        stdev = statistics.pstdev(values)
        if stdev > 0:
            for file, value in counted:
                z = (value - mean) / stdev
                if abs(z) >= entity_z:
                    findings.append(
                        {"file": file, "reason": f"entity_count outlier (z={z:.2f})"}
                    )

    return findings


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query a corpus-batch JSONL ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    summarize_parser = sub.add_parser("summarize", help="print aggregate counts")
    summarize_parser.add_argument("ledger", help="path to the JSONL ledger")

    anomalies_parser = sub.add_parser("anomalies", help="print failure and outlier rows")
    anomalies_parser.add_argument("ledger", help="path to the JSONL ledger")
    anomalies_parser.add_argument(
        "--entity-z",
        type=float,
        default=3.0,
        help="z-score threshold for entity-count outliers (default: 3.0)",
    )

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    rows = load_ledger(args.ledger)
    if args.command == "summarize":
        result: Any = summarize(rows)
    else:
        result = anomalies(rows, entity_z=args.entity_z)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
