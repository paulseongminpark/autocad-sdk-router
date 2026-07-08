#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate ariadne.roundtrip_report.v1 documents against the schema of record."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)
_SCHEMA_PATH = os.path.join(_ROUTER_HOME, "schemas", "roundtrip_report.v1.schema.json")
_JSON_ENCODING = "utf-8-sig"

REPORT_SCHEMA_ID = "ariadne.roundtrip_report.v1"
_KIND_STATUSES = frozenset({"PASS", "FAIL", "VACUOUS"})
_JUDGMENTS = frozenset({"harmless", "harmful", "unreviewed"})
_CEILING_KEYS = (
    "modelspace_entity_total",
    "certified_total",
    "out_of_class_total",
    "deferred_count",
)
_KIND_COUNT_KEYS = (
    "census_count",
    "attempted_count",
    "diff0_count",
    "modified_count",
    "removed_count",
    "added_count",
)
_TOP_REQUIRED = (
    "schema",
    "run_dir",
    "ceiling",
    "kind_buckets",
    "patterns",
    "naive_vs_smart",
    "totals",
)


def _path_join(prefix: str, part: str) -> str:
    return part if not prefix else f"{prefix}/{part}"


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _check_object(
    value: Any,
    path: str,
    errors: list[str],
    *,
    required: tuple[str, ...] | None = None,
) -> dict | None:
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object")
        return None
    if required:
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required key: {key}")
    return value


def _check_non_negative_int_field(
    obj: dict,
    key: str,
    path: str,
    errors: list[str],
    *,
    required: bool = True,
) -> None:
    if key not in obj:
        if required:
            errors.append(f"{path}: missing required key: {key}")
        return
    val = obj.get(key)
    if not _is_non_negative_int(val):
        errors.append(f"{path}/{key}: must be a non-negative integer, got {val!r}")


def _check_ceiling(ceiling: Any, path: str, errors: list[str]) -> None:
    obj = _check_object(ceiling, path, errors, required=_CEILING_KEYS)
    if obj is None:
        return
    for key in _CEILING_KEYS:
        _check_non_negative_int_field(obj, key, path, errors)


def _check_kind_bucket(bucket: Any, path: str, errors: list[str]) -> None:
    obj = _check_object(
        bucket,
        path,
        errors,
        required=("status", "certified", *_KIND_COUNT_KEYS),
    )
    if obj is None:
        return
    status = obj.get("status")
    if status not in _KIND_STATUSES:
        errors.append(
            f"{path}/status: must be one of PASS/FAIL/VACUOUS, got {status!r}"
        )
    certified = obj.get("certified")
    if not isinstance(certified, bool):
        errors.append(f"{path}/certified: must be a boolean, got {certified!r}")
    for key in _KIND_COUNT_KEYS:
        _check_non_negative_int_field(obj, key, path, errors)


def _check_kind_buckets(kind_buckets: Any, path: str, errors: list[str]) -> None:
    obj = _check_object(kind_buckets, path, errors)
    if obj is None:
        return
    for name, bucket in obj.items():
        _check_kind_bucket(bucket, _path_join(path, str(name)), errors)


def _check_pattern_signature(signature: Any, path: str, errors: list[str]) -> None:
    obj = _check_object(signature, path, errors, required=("dxf_name", "change", "context"))
    if obj is None:
        return
    for key in ("dxf_name", "change", "context"):
        val = obj.get(key)
        if not isinstance(val, str):
            errors.append(f"{path}/{key}: must be a string, got {val!r}")


def _check_pattern(pattern: Any, path: str, errors: list[str]) -> None:
    obj = _check_object(pattern, path, errors, required=("signature", "count", "judgment"))
    if obj is None:
        return
    _check_pattern_signature(obj.get("signature"), _path_join(path, "signature"), errors)
    _check_non_negative_int_field(obj, "count", path, errors)
    judgment = obj.get("judgment")
    if judgment not in _JUDGMENTS:
        errors.append(
            f"{path}/judgment: must be one of harmless/harmful/unreviewed, got {judgment!r}"
        )
    examples = obj.get("examples")
    if examples is not None:
        if not isinstance(examples, list):
            errors.append(f"{path}/examples: must be an array")
        elif len(examples) > 3:
            errors.append(f"{path}/examples: must have at most 3 items, got {len(examples)}")


def _check_patterns(patterns: Any, path: str, errors: list[str]) -> None:
    if not isinstance(patterns, list):
        errors.append(f"{path}: must be an array")
        return
    for index, pattern in enumerate(patterns):
        _check_pattern(pattern, _path_join(path, str(index)), errors)


def _check_naive_vs_smart(naive_vs_smart: Any, path: str, errors: list[str]) -> None:
    obj = _check_object(
        naive_vs_smart,
        path,
        errors,
        required=("naive_pass", "smart_all_diff0", "contrast_note"),
    )
    if obj is None:
        return
    for key in ("naive_pass", "smart_all_diff0"):
        val = obj.get(key)
        if not isinstance(val, bool):
            errors.append(f"{path}/{key}: must be a boolean, got {val!r}")
    note = obj.get("contrast_note")
    if not isinstance(note, str):
        errors.append(f"{path}/contrast_note: must be a string, got {note!r}")


def validate_report_structural(doc: Any) -> list[str]:
    """Structural fallback validator implementing the pinned roundtrip_report.v1 checks."""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["<root>: must be an object"]

    for key in _TOP_REQUIRED:
        if key not in doc:
            errors.append(f"<root>: missing required key: {key}")

    schema = doc.get("schema")
    if schema != REPORT_SCHEMA_ID:
        errors.append(f"schema: const mismatch: expected {REPORT_SCHEMA_ID!r}, got {schema!r}")

    run_dir = doc.get("run_dir")
    if not isinstance(run_dir, str):
        errors.append(f"run_dir: must be a string, got {run_dir!r}")

    _check_ceiling(doc.get("ceiling"), "ceiling", errors)
    _check_kind_buckets(doc.get("kind_buckets"), "kind_buckets", errors)
    _check_patterns(doc.get("patterns"), "patterns", errors)
    _check_naive_vs_smart(doc.get("naive_vs_smart"), "naive_vs_smart", errors)

    totals = doc.get("totals")
    if not isinstance(totals, dict):
        errors.append("totals: must be an object")

    return errors


def _validate_with_jsonschema(doc: dict) -> list[str]:
    import jsonschema  # type: ignore

    with open(_SCHEMA_PATH, "r", encoding=_JSON_ENCODING) as fh:
        schema = json.load(fh)
    validator = jsonschema.Draft7Validator(schema)
    return [
        "%s: %s" % ("/".join(str(part) for part in err.path) or "<root>", err.message)
        for err in sorted(validator.iter_errors(doc), key=lambda item: list(item.path))
    ]


def validate_report_doc(doc: Any) -> list[str]:
    """Validate a roundtrip report document. Returns a list of error strings (empty if valid)."""
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        return validate_report_structural(doc)
    return _validate_with_jsonschema(doc)


def load_report(path: str) -> Any:
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate ariadne.roundtrip_report.v1 JSON documents."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="Validate a report JSON file.")
    validate_parser.add_argument("report_json", help="Path to roundtrip_report JSON.")
    args = parser.parse_args(argv)

    if args.command != "validate":
        parser.error(f"unknown command: {args.command}")
        return 2

    doc = load_report(args.report_json)
    errors = validate_report_doc(doc)
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
