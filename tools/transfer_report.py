#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""transfer_report: PURE-JSON aggregator for parallel_roundtrip_sweep outputs.

Reads a sweep root (parallel_sweep_summary.json + per-drawing subdirs) and emits
a cross-drawing generalization report. Stdlib only — no engine/router/subprocess.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

REPORT_SCHEMA = "ariadne.transfer_report.v1"
HONESTY_NOTE = (
    "blocked/partial drawings carry no diff signal; they are reported, not hidden"
)


def read_json(path: str) -> dict | list | None:
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def write_json(path: str, obj: dict) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def extract_out_of_class_kinds(census_report: dict | None) -> dict[str, int]:
    """Derive out_of_class_kinds from census buckets without guessing."""
    kinds: dict[str, int] = {}
    if not isinstance(census_report, dict):
        return kinds

    by_bucket = census_report.get("by_bucket") or []
    certified_pairs: set[tuple[str, str]] = set()
    has_certified_info = False

    for bucket in by_bucket:
        if not isinstance(bucket, dict):
            continue
        dxf = str(bucket.get("dxf_name") or "")
        kind = str(bucket.get("kind") or "")
        count = int(bucket.get("count") or 0)
        certified = bucket.get("certified")
        if certified is True:
            has_certified_info = True
            certified_pairs.add((dxf, kind))
        elif certified is False:
            has_certified_info = True
            if kind:
                kinds[kind] = kinds.get(kind, 0) + count

    if has_certified_info and certified_pairs:
        for bucket in census_report.get("block_definitions_by_bucket") or []:
            if not isinstance(bucket, dict):
                continue
            dxf = str(bucket.get("dxf_name") or "")
            kind = str(bucket.get("kind") or "")
            count = int(bucket.get("count") or 0)
            if kind and (dxf, kind) not in certified_pairs:
                kinds[kind] = kinds.get(kind, 0) + count

    return kinds


def _terminal_status_from_summary(summary: dict | None, verdict_present: bool) -> str:
    if verdict_present:
        return "success"
    if not isinstance(summary, dict):
        return "blocked"
    status = summary.get("status")
    if status in ("exhausted",):
        return "exhausted"
    if status in ("blocked",):
        return "blocked"
    if status in ("ok", "success") and verdict_present:
        return "success"
    return "blocked"


def _coerce_fraction(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_report(sweep_root: str) -> dict:
    sweep_root = os.path.abspath(sweep_root)
    sweep_summary = read_json(os.path.join(sweep_root, "parallel_sweep_summary.json"))
    if not isinstance(sweep_summary, dict):
        sweep_summary = {}

    results_by_slug: dict[str, dict] = {}
    ordered_entries: list[tuple[str, str, dict | None]] = []
    seen_slugs: set[str] = set()

    for result in sweep_summary.get("results") or []:
        if not isinstance(result, dict):
            continue
        out_dir = str(result.get("out_dir") or "")
        slug = os.path.basename(out_dir.rstrip("/\\"))
        if not slug:
            continue
        results_by_slug[slug] = result
        if slug not in seen_slugs:
            seen_slugs.add(slug)
            ordered_entries.append((slug, out_dir, result))

    try:
        names = sorted(os.listdir(sweep_root))
    except OSError:
        names = []

    for name in names:
        path = os.path.join(sweep_root, name)
        if not os.path.isdir(path) or name in seen_slugs:
            continue
        seen_slugs.add(name)
        ordered_entries.append((name, path, results_by_slug.get(name)))

    drawings: list[dict] = []

    for slug, out_dir, sweep_result in ordered_entries:
        if not out_dir:
            out_dir = os.path.join(sweep_root, slug)

        summary = read_json(os.path.join(out_dir, "summary.json"))
        if not isinstance(summary, dict):
            summary = {}

        verdict_data = read_json(os.path.join(out_dir, "verdict.json"))
        interior = read_json(os.path.join(out_dir, "interior_diff.json"))

        verdict_present = False
        if isinstance(sweep_result, dict) and "verdict_present" in sweep_result:
            verdict_present = bool(sweep_result.get("verdict_present"))
        else:
            verdict_present = verdict_data is not None

        fraction: float | None = None
        if isinstance(sweep_result, dict) and sweep_result.get("interior_diff0_fraction") is not None:
            fraction = _coerce_fraction(sweep_result.get("interior_diff0_fraction"))
        elif isinstance(interior, dict):
            fraction = _coerce_fraction(interior.get("interior_diff0_fraction"))

        terminal_status = "blocked"
        if isinstance(sweep_result, dict) and sweep_result.get("status") in (
            "success",
            "blocked",
            "exhausted",
        ):
            terminal_status = str(sweep_result["status"])
        else:
            terminal_status = _terminal_status_from_summary(summary, verdict_present)

        capstone_status = None
        if isinstance(sweep_result, dict) and sweep_result.get("capstone_status") is not None:
            capstone_status = sweep_result.get("capstone_status")
        elif summary.get("status") is not None:
            capstone_status = summary.get("status")

        drawing_name = slug
        if isinstance(sweep_result, dict) and sweep_result.get("drawing"):
            drawing_name = str(sweep_result["drawing"])

        census_report = summary.get("census_report") or {}
        if not isinstance(census_report, dict):
            census_report = {}

        regen = summary.get("regen") or {}
        if not isinstance(regen, dict):
            regen = {}
        gate = regen.get("gate") or {}
        if not isinstance(gate, dict):
            gate = {}

        drawings.append(
            {
                "drawing": drawing_name,
                "slug": slug,
                "capstone_status": capstone_status,
                "verdict_present": verdict_present,
                "interior_diff0_fraction": fraction,
                "census": {
                    "modelspace_entity_total": int(census_report.get("modelspace_entity_total") or 0),
                    "certified_total": int(census_report.get("certified_total") or 0),
                    "out_of_class_total": int(census_report.get("out_of_class_total") or 0),
                    "out_of_class_kinds": extract_out_of_class_kinds(census_report),
                },
                "regen": {
                    "op_count": int(regen.get("op_count") or 0),
                    "apply_status": str(regen.get("apply_status") or ""),
                    "gate_ok": bool(gate.get("ok")),
                },
                "terminal_status": terminal_status,
            }
        )

    fractions = [
        d["interior_diff0_fraction"]
        for d in drawings
        if d.get("interior_diff0_fraction") is not None
    ]
    mean_fraction = statistics.mean(fractions) if fractions else None
    min_fraction = min(fractions) if fractions else None

    union_kinds: dict[str, int] = {}
    for drawing in drawings:
        for kind, count in (drawing.get("census") or {}).get("out_of_class_kinds", {}).items():
            union_kinds[kind] = union_kinds.get(kind, 0) + int(count)

    without_verdict = [d["slug"] for d in drawings if not d.get("verdict_present")]

    return {
        "schema": REPORT_SCHEMA,
        "sweep_root": sweep_root,
        "drawings": drawings,
        "rollup": {
            "drawing_count": len(drawings),
            "succeeded": sum(1 for d in drawings if d.get("terminal_status") == "success"),
            "blocked": sum(1 for d in drawings if d.get("terminal_status") == "blocked"),
            "mean_interior_diff0_fraction": mean_fraction,
            "min_interior_diff0_fraction": min_fraction,
            "out_of_class_kinds_union": union_kinds,
        },
        "honesty": {
            "drawings_without_verdict": without_verdict,
            "note": HONESTY_NOTE,
        },
    }


def print_table(drawings: list[dict]) -> None:
    header = f"{'slug':<20} {'terminal_status':<16} {'diff0_fraction':>14} {'op_count':>8}"
    print(header)
    print("-" * len(header))
    for drawing in drawings:
        fraction = drawing.get("interior_diff0_fraction")
        fraction_s = "" if fraction is None else f"{fraction:g}"
        op_count = (drawing.get("regen") or {}).get("op_count", 0)
        print(
            f"{drawing.get('slug', ''):<20} "
            f"{drawing.get('terminal_status', ''):<16} "
            f"{fraction_s:>14} "
            f"{op_count:>8}"
        )


def build_transfer_report(sweep_root: str, out_path: str | None = None) -> dict:
    """Build report, optionally write JSON, always print the human table."""
    report = build_report(sweep_root)
    if out_path is None:
        out_path = os.path.join(os.path.abspath(sweep_root), "transfer_report.json")
    write_json(out_path, report)
    print_table(report.get("drawings") or [])
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sweep-root", required=True, help="parallel_roundtrip_sweep output directory")
    ap.add_argument(
        "--out",
        default=None,
        help="output JSON path (default: <sweep-root>/transfer_report.json)",
    )
    args = ap.parse_args(argv)
    out_path = args.out or os.path.join(os.path.abspath(args.sweep_root), "transfer_report.json")
    build_transfer_report(args.sweep_root, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
