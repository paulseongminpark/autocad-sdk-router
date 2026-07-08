#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed equivalence check for capstone batch-vs-per-op runs."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA_ID = "ariadne.batch_equivalence.v1"
DIFF_ARTIFACT = "geometry_diff.json"
ARTIFACT_ERROR_CODES = {"MISSING_ARTIFACT", "CORRUPT_ARTIFACT"}
VERDICT_REQUIRED_COUNTS = (
    "regen_attempted_count",
    "diff0_count",
    "modified_count",
    "removed_count",
    "added_count",
)
DIFF_REQUIRED_COUNTS = ("added", "removed", "modified")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _json_file_path(run_dir: str, filename: str) -> str:
    return os.path.join(run_dir, filename)


def _format_value(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return repr(value)


def _add_mismatch(
    mismatches: List[Dict[str, Any]],
    path: str,
    field: str,
    a_value: Any,
    b_value: Any,
    *,
    code: Optional[str] = None,
) -> None:
    row = {
        "path": path,
        "field": field,
        "a_value": a_value,
        "b_value": b_value,
    }
    if code:
        row["code"] = code
    mismatches.append(row)


def _load_json(
    run_dir_a: str,
    run_dir_b: str,
    filename: str,
    mismatches: List[Dict[str, Any]],
    *,
    required_in_a: bool = True,
    required_in_b: bool = True,
) -> Tuple[Optional[Any], Optional[Any]]:
    path_a = _json_file_path(run_dir_a, filename)
    path_b = _json_file_path(run_dir_b, filename)

    payload_a: Optional[Any] = None
    payload_b: Optional[Any] = None

    exists_a = os.path.isfile(path_a)
    exists_b = os.path.isfile(path_b)

    if required_in_a and not exists_a:
        _add_mismatch(
            mismatches,
            filename,
            "artifact",
            "missing",
            "present" if exists_b else "missing",
            code="MISSING_ARTIFACT",
        )
    if required_in_b and not exists_b:
        _add_mismatch(
            mismatches,
            filename,
            "artifact",
            "present" if exists_a else "missing",
            "missing",
            code="MISSING_ARTIFACT",
        )

    if exists_a:
        try:
            with open(path_a, encoding="utf-8-sig") as handle:
                payload_a = json.load(handle)
        except (OSError, ValueError) as exc:
            _add_mismatch(
                mismatches,
                filename,
                "artifact",
                f"corrupt: {exc}",
                "present" if exists_b else "missing",
                code="CORRUPT_ARTIFACT",
            )
    if exists_b:
        try:
            with open(path_b, encoding="utf-8-sig") as handle:
                payload_b = json.load(handle)
        except (OSError, ValueError) as exc:
            _add_mismatch(
                mismatches,
                filename,
                "artifact",
                "present" if exists_a else "missing",
                f"corrupt: {exc}",
                code="CORRUPT_ARTIFACT",
            )

    return payload_a, payload_b


def _validate_summary(
    payload: Any,
    filename: str,
    side: str,
    mismatches: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        _add_mismatch(mismatches, filename, "artifact", side, type(payload).__name__, code="CORRUPT_ARTIFACT")
        return None
    regen = payload.get("regen")
    staged = payload.get("staged")
    status = payload.get("status")
    if not isinstance(regen, dict) or not _is_int(regen.get("op_count")):
        _add_mismatch(
            mismatches,
            filename,
            "regen.op_count",
            side,
            regen.get("op_count") if isinstance(regen, dict) else regen,
            code="CORRUPT_ARTIFACT",
        )
        return None
    if not isinstance(staged, dict) or not isinstance(staged.get("original_sha256"), str):
        _add_mismatch(
            mismatches,
            filename,
            "staged.original_sha256",
            side,
            staged.get("original_sha256") if isinstance(staged, dict) else staged,
            code="CORRUPT_ARTIFACT",
        )
        return None
    if status is None:
        _add_mismatch(mismatches, filename, "status", side, status, code="CORRUPT_ARTIFACT")
        return None
    return payload


def _validate_verdict(
    payload: Any,
    filename: str,
    side: str,
    mismatches: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        _add_mismatch(mismatches, filename, "artifact", side, type(payload).__name__, code="CORRUPT_ARTIFACT")
        return None
    rows = payload.get("rows")
    totals = payload.get("totals")
    if not isinstance(rows, list) or not isinstance(totals, dict):
        _add_mismatch(
            mismatches,
            filename,
            "artifact",
            side,
            {"rows_type": type(rows).__name__, "totals_type": type(totals).__name__},
            code="CORRUPT_ARTIFACT",
        )
        return None

    rows_by_dxf: Dict[str, Dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            _add_mismatch(mismatches, filename, f"rows[{index}]", side, type(row).__name__, code="CORRUPT_ARTIFACT")
            return None
        dxf_name = row.get("dxf_name")
        if not isinstance(dxf_name, str):
            _add_mismatch(mismatches, filename, f"rows[{index}].dxf_name", side, dxf_name, code="CORRUPT_ARTIFACT")
            return None
        if dxf_name in rows_by_dxf:
            _add_mismatch(mismatches, filename, f"rows[{index}].dxf_name", side, dxf_name, code="CORRUPT_ARTIFACT")
            return None
        for field in VERDICT_REQUIRED_COUNTS:
            if not _is_int(row.get(field)):
                _add_mismatch(
                    mismatches,
                    filename,
                    f"rows[{dxf_name}].{field}",
                    side,
                    row.get(field),
                    code="CORRUPT_ARTIFACT",
                )
                return None
        for key, value in row.items():
            if key.endswith("_count") and key not in VERDICT_REQUIRED_COUNTS and not _is_int(value):
                _add_mismatch(
                    mismatches,
                    filename,
                    f"rows[{dxf_name}].{key}",
                    side,
                    value,
                    code="CORRUPT_ARTIFACT",
                )
                return None
        rows_by_dxf[dxf_name] = row

    for field in VERDICT_REQUIRED_COUNTS:
        if not _is_int(totals.get(field)):
            _add_mismatch(mismatches, filename, f"totals.{field}", side, totals.get(field), code="CORRUPT_ARTIFACT")
            return None
    for key, value in totals.items():
        if key.endswith("_count") and key not in VERDICT_REQUIRED_COUNTS and not _is_int(value):
            _add_mismatch(mismatches, filename, f"totals.{key}", side, value, code="CORRUPT_ARTIFACT")
            return None

    return {"rows": rows_by_dxf, "totals": totals}


def _validate_deferred(
    payload: Any,
    filename: str,
    side: str,
    mismatches: List[Dict[str, Any]],
) -> Optional[Counter]:
    if not isinstance(payload, list):
        _add_mismatch(mismatches, filename, "artifact", side, type(payload).__name__, code="CORRUPT_ARTIFACT")
        return None
    pairs: Counter = Counter()
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            _add_mismatch(mismatches, filename, f"rows[{index}]", side, type(row).__name__, code="CORRUPT_ARTIFACT")
            return None
        kind = row.get("kind")
        reason = row.get("reason")
        if not isinstance(kind, str) or not isinstance(reason, str):
            _add_mismatch(
                mismatches,
                filename,
                f"rows[{index}]",
                side,
                {"kind": kind, "reason": reason},
                code="CORRUPT_ARTIFACT",
            )
            return None
        pairs[(kind, reason)] += 1
    return pairs


def _validate_diff(
    payload: Any,
    filename: str,
    side: str,
    mismatches: List[Dict[str, Any]],
) -> Optional[Dict[str, Dict[str, int]]]:
    if not isinstance(payload, dict):
        _add_mismatch(mismatches, filename, "artifact", side, type(payload).__name__, code="CORRUPT_ARTIFACT")
        return None
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        _add_mismatch(mismatches, filename, "summary", side, summary, code="CORRUPT_ARTIFACT")
        return None
    by_type = summary.get("by_type")
    if not isinstance(by_type, dict):
        _add_mismatch(mismatches, filename, "summary.by_type", side, by_type, code="CORRUPT_ARTIFACT")
        return None

    normalized: Dict[str, Dict[str, int]] = {}
    for dxf_name, counts in by_type.items():
        if not isinstance(counts, dict):
            _add_mismatch(mismatches, filename, f"summary.by_type[{dxf_name}]", side, counts, code="CORRUPT_ARTIFACT")
            return None
        normalized[str(dxf_name)] = {}
        for field in DIFF_REQUIRED_COUNTS:
            value = counts.get(field, 0)
            if not _is_int(value):
                _add_mismatch(
                    mismatches,
                    filename,
                    f"summary.by_type[{dxf_name}].{field}",
                    side,
                    value,
                    code="CORRUPT_ARTIFACT",
                )
                return None
            normalized[str(dxf_name)][field] = value
    return normalized


def _shared_optional_count_fields(a_row: Dict[str, Any], b_row: Dict[str, Any]) -> Iterable[str]:
    shared = set(a_row).intersection(b_row)
    return sorted(
        key for key in shared
        if key.endswith("_count") and key not in VERDICT_REQUIRED_COUNTS
    )


def _compare_verdict(
    verdict_a: Dict[str, Any],
    verdict_b: Dict[str, Any],
    mismatches: List[Dict[str, Any]],
) -> None:
    rows_a = verdict_a["rows"]
    rows_b = verdict_b["rows"]
    for dxf_name in sorted(set(rows_a).union(rows_b)):
        row_a = rows_a.get(dxf_name)
        row_b = rows_b.get(dxf_name)
        if row_a is None or row_b is None:
            _add_mismatch(mismatches, "verdict.json", f"rows[{dxf_name}]", row_a, row_b)
            continue
        for field in VERDICT_REQUIRED_COUNTS:
            if row_a[field] != row_b[field]:
                _add_mismatch(
                    mismatches,
                    "verdict.json",
                    f"rows[{dxf_name}].{field}",
                    row_a[field],
                    row_b[field],
                )
        for field in _shared_optional_count_fields(row_a, row_b):
            if row_a[field] != row_b[field]:
                _add_mismatch(
                    mismatches,
                    "verdict.json",
                    f"rows[{dxf_name}].{field}",
                    row_a[field],
                    row_b[field],
                )

    totals_a = verdict_a["totals"]
    totals_b = verdict_b["totals"]
    for field in VERDICT_REQUIRED_COUNTS:
        if totals_a[field] != totals_b[field]:
            _add_mismatch(mismatches, "verdict.json", f"totals.{field}", totals_a[field], totals_b[field])
    for field in _shared_optional_count_fields(totals_a, totals_b):
        if totals_a[field] != totals_b[field]:
            _add_mismatch(mismatches, "verdict.json", f"totals.{field}", totals_a[field], totals_b[field])


def _compare_summary(
    summary_a: Dict[str, Any],
    summary_b: Dict[str, Any],
    mismatches: List[Dict[str, Any]],
) -> None:
    if summary_a["regen"]["op_count"] != summary_b["regen"]["op_count"]:
        _add_mismatch(
            mismatches,
            "summary.json",
            "regen.op_count",
            summary_a["regen"]["op_count"],
            summary_b["regen"]["op_count"],
        )
    if summary_a["status"] != summary_b["status"]:
        _add_mismatch(mismatches, "summary.json", "status", summary_a["status"], summary_b["status"])
    sha_a = summary_a["staged"]["original_sha256"]
    sha_b = summary_b["staged"]["original_sha256"]
    if sha_a != sha_b:
        _add_mismatch(
            mismatches,
            "summary.json",
            "staged.original_sha256",
            sha_a,
            sha_b,
            code="DIFFERENT_SOURCE",
        )


def _compare_deferred(
    deferred_a: Counter,
    deferred_b: Counter,
    mismatches: List[Dict[str, Any]],
) -> None:
    for pair in sorted(set(deferred_a).union(deferred_b)):
        count_a = deferred_a.get(pair, 0)
        count_b = deferred_b.get(pair, 0)
        if count_a != count_b:
            kind, reason = pair
            _add_mismatch(
                mismatches,
                "deferred.json",
                f"pairs[{kind!r}, {reason!r}]",
                count_a,
                count_b,
            )


def _compare_diff(
    diff_a: Dict[str, Dict[str, int]],
    diff_b: Dict[str, Dict[str, int]],
    mismatches: List[Dict[str, Any]],
) -> None:
    for dxf_name in sorted(set(diff_a).union(diff_b)):
        counts_a = diff_a.get(dxf_name, {})
        counts_b = diff_b.get(dxf_name, {})
        for field in DIFF_REQUIRED_COUNTS:
            value_a = counts_a.get(field, 0)
            value_b = counts_b.get(field, 0)
            if value_a != value_b:
                _add_mismatch(
                    mismatches,
                    DIFF_ARTIFACT,
                    f"summary.by_type[{dxf_name}].{field}",
                    value_a,
                    value_b,
                )


def _has_artifact_errors(mismatches: Iterable[Dict[str, Any]]) -> bool:
    return any(mismatch.get("code") in ARTIFACT_ERROR_CODES for mismatch in mismatches)


def check_equivalence(run_dir_a: str, run_dir_b: str) -> Dict[str, Any]:
    run_dir_a = os.path.abspath(run_dir_a)
    run_dir_b = os.path.abspath(run_dir_b)
    mismatches: List[Dict[str, Any]] = []
    compared = {
        "run_dir_a": run_dir_a,
        "run_dir_b": run_dir_b,
        "artifacts": {
            "summary": _json_file_path(run_dir_a, "summary.json"),
            "verdict": _json_file_path(run_dir_a, "verdict.json"),
            "diff": _json_file_path(run_dir_a, DIFF_ARTIFACT),
            "deferred_compared": False,
        },
    }

    summary_a_payload, summary_b_payload = _load_json(run_dir_a, run_dir_b, "summary.json", mismatches)
    verdict_a_payload, verdict_b_payload = _load_json(run_dir_a, run_dir_b, "verdict.json", mismatches)
    diff_a_payload, diff_b_payload = _load_json(run_dir_a, run_dir_b, DIFF_ARTIFACT, mismatches)

    summary_a = _validate_summary(summary_a_payload, "summary.json", "a", mismatches) if summary_a_payload is not None else None
    summary_b = _validate_summary(summary_b_payload, "summary.json", "b", mismatches) if summary_b_payload is not None else None
    verdict_a = _validate_verdict(verdict_a_payload, "verdict.json", "a", mismatches) if verdict_a_payload is not None else None
    verdict_b = _validate_verdict(verdict_b_payload, "verdict.json", "b", mismatches) if verdict_b_payload is not None else None
    diff_a = _validate_diff(diff_a_payload, DIFF_ARTIFACT, "a", mismatches) if diff_a_payload is not None else None
    diff_b = _validate_diff(diff_b_payload, DIFF_ARTIFACT, "b", mismatches) if diff_b_payload is not None else None

    deferred_a_path = _json_file_path(run_dir_a, "deferred.json")
    deferred_b_path = _json_file_path(run_dir_b, "deferred.json")
    deferred_a_exists = os.path.isfile(deferred_a_path)
    deferred_b_exists = os.path.isfile(deferred_b_path)
    deferred_a: Optional[Counter] = None
    deferred_b: Optional[Counter] = None
    if deferred_a_exists or deferred_b_exists:
        compared["artifacts"]["deferred_compared"] = True
        deferred_a_payload, deferred_b_payload = _load_json(
            run_dir_a,
            run_dir_b,
            "deferred.json",
            mismatches,
            required_in_a=deferred_a_exists or deferred_b_exists,
            required_in_b=deferred_a_exists or deferred_b_exists,
        )
        deferred_a = _validate_deferred(deferred_a_payload, "deferred.json", "a", mismatches) if deferred_a_payload is not None else None
        deferred_b = _validate_deferred(deferred_b_payload, "deferred.json", "b", mismatches) if deferred_b_payload is not None else None

    if summary_a is not None and summary_b is not None:
        _compare_summary(summary_a, summary_b, mismatches)
    if verdict_a is not None and verdict_b is not None:
        _compare_verdict(verdict_a, verdict_b, mismatches)
    if diff_a is not None and diff_b is not None:
        _compare_diff(diff_a, diff_b, mismatches)
    if deferred_a is not None and deferred_b is not None:
        _compare_deferred(deferred_a, deferred_b, mismatches)

    equivalent = not mismatches
    exit_code = 3 if _has_artifact_errors(mismatches) else (0 if equivalent else 2)
    return {
        "schema": SCHEMA_ID,
        "equivalent": equivalent,
        "mismatches": mismatches,
        "compared": compared,
        "exit_code": exit_code,
    }


def _stdout_report(result: Dict[str, Any]) -> None:
    mismatches = result["mismatches"]
    if not mismatches:
        print("Equivalent: no mismatches found.")
        return
    for mismatch in mismatches:
        code = mismatch.get("code")
        prefix = f"{code} " if code else ""
        print(
            f"{prefix}{mismatch['path']} {mismatch['field']} "
            f"a={_format_value(mismatch['a_value'])} "
            f"b={_format_value(mismatch['b_value'])}"
        )


def _write_out_json(path: str, result: Dict[str, Any]) -> None:
    payload = {
        "schema": SCHEMA_ID,
        "equivalent": result["equivalent"],
        "mismatches": result["mismatches"],
        "compared": result["compared"],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check equivalence of two full_roundtrip_capstone runs.")
    parser.add_argument("run_dir_a")
    parser.add_argument("run_dir_b")
    parser.add_argument("--out-json", dest="out_json", default=None)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = check_equivalence(args.run_dir_a, args.run_dir_b)
    _stdout_report(result)
    if args.out_json:
        _write_out_json(args.out_json, result)
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
