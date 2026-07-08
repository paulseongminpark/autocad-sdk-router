#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R4 corpus sweep: run capstone census-only across many DWGs and aggregate.

Stdlib only. See docs/E2E_ROUNDTRIP_TEST_PLAN.md (R4 stage).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAPSTONE_SCRIPT = ROOT / "tools" / "full_roundtrip_capstone.py"
SWEEP_PLAN_SCHEMA = "ariadne.roundtrip_sweep_plan.v1"
CENSUS_SUMMARY_SCHEMA = "ariadne.roundtrip_corpus_census.v1"
SWEEP_PLAN_FILE = "sweep_plan.json"
SWEEP_RESULTS_FILE = "sweep_results.json"
CENSUS_SUMMARY_JSON = "corpus_census_summary.json"
CENSUS_SUMMARY_MD = "corpus_census_summary.md"


def load_dwg_list(path: str | Path) -> list[str]:
    """Load absolute DWG paths from a text file (blank lines and # comments skipped)."""
    paths: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            paths.append(os.path.abspath(stripped))
    return paths


def out_dir_name(ordinal: int, dwg_path: str) -> str:
    stem = Path(dwg_path).stem
    safe_stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stem)
    safe_stem = safe_stem.strip("._") or "unnamed"
    return f"{ordinal:03d}_{safe_stem}"


def build_capstone_cmd(
    *,
    python_exe: str,
    dwg_path: str,
    out_dir: str,
) -> list[str]:
    return [
        python_exe,
        str(CAPSTONE_SCRIPT),
        "--dwg",
        dwg_path,
        "--out-dir",
        out_dir,
        "--census-only",
        "--skip-identity",
    ]


def build_sweep_plan(
    dwg_paths: list[str],
    out_root: str,
    *,
    python_exe: str,
) -> dict[str, Any]:
    out_root_abs = os.path.abspath(out_root)
    entries: list[dict[str, Any]] = []
    for ordinal, dwg_path in enumerate(dwg_paths, start=1):
        out_dir = os.path.join(out_root_abs, out_dir_name(ordinal, dwg_path))
        entries.append(
            {
                "dwg": dwg_path,
                "out_dir": out_dir,
                "cmd": build_capstone_cmd(
                    python_exe=python_exe,
                    dwg_path=dwg_path,
                    out_dir=out_dir,
                ),
            }
        )
    return {"schema": SWEEP_PLAN_SCHEMA, "entries": entries}


def _write_json(path: str | Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_census_report(out_dir: str) -> dict[str, Any] | None:
    report_path = os.path.join(out_dir, "census_report.json")
    if not os.path.isfile(report_path):
        return None
    with open(report_path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def _load_plan_entries(out_root: str) -> list[dict[str, Any]]:
    plan_path = os.path.join(out_root, SWEEP_PLAN_FILE)
    if os.path.isfile(plan_path):
        with open(plan_path, encoding="utf-8-sig") as fh:
            plan = json.load(fh)
        return list(plan.get("entries") or [])

    entries: list[dict[str, Any]] = []
    root = Path(out_root)
    if not root.is_dir():
        return entries
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if (child / "census_report.json").is_file():
            entries.append({"dwg": "", "out_dir": str(child.resolve())})
    return entries


def aggregate_census(out_root: str) -> dict[str, Any]:
    """Aggregate per-drawing census_report.json files under *out_root*."""
    out_root_abs = os.path.abspath(out_root)
    plan_entries = _load_plan_entries(out_root_abs)

    drawings: list[dict[str, Any]] = []
    per_dxf_counts: dict[str, int] = {}
    per_dxf_drawings: dict[str, set[str]] = {}
    per_dxf_certified: dict[str, bool] = {}

    census_ok = 0
    modelspace_total = 0

    for entry in plan_entries:
        dwg = str(entry.get("dwg") or "")
        out_dir = str(entry.get("out_dir") or "")
        report = _read_census_report(out_dir)
        if report is None:
            drawings.append(
                {
                    "dwg": dwg,
                    "ok": False,
                    "modelspace_entity_total": None,
                    "certified_total": None,
                    "out_of_class_total": None,
                }
            )
            continue

        ms_total = int(report.get("modelspace_entity_total") or 0)
        cert_total = int(report.get("certified_total") or 0)
        ooc_total = int(report.get("out_of_class_total") or 0)
        drawings.append(
            {
                "dwg": dwg,
                "ok": True,
                "modelspace_entity_total": ms_total,
                "certified_total": cert_total,
                "out_of_class_total": ooc_total,
            }
        )
        census_ok += 1
        modelspace_total += ms_total

        drawing_key = dwg or out_dir
        for bucket in report.get("by_bucket") or []:
            if not isinstance(bucket, dict):
                continue
            dxf_name = str(bucket.get("dxf_name") or "")
            if not dxf_name:
                continue
            count = int(bucket.get("count") or 0)
            certified = bool(bucket.get("certified"))
            per_dxf_counts[dxf_name] = per_dxf_counts.get(dxf_name, 0) + count
            per_dxf_drawings.setdefault(dxf_name, set()).add(drawing_key)
            if dxf_name not in per_dxf_certified:
                per_dxf_certified[dxf_name] = certified
            elif per_dxf_certified[dxf_name] and not certified:
                per_dxf_certified[dxf_name] = False

    per_dxf: dict[str, dict[str, Any]] = {}
    for dxf_name in sorted(per_dxf_counts):
        per_dxf[dxf_name] = {
            "total_count": per_dxf_counts[dxf_name],
            "drawings_present": len(per_dxf_drawings.get(dxf_name, set())),
            "certified": per_dxf_certified.get(dxf_name, False),
        }

    return {
        "schema": CENSUS_SUMMARY_SCHEMA,
        "drawings": drawings,
        "per_dxf": per_dxf,
        "totals": {
            "drawings": len(drawings),
            "census_ok": census_ok,
            "modelspace_entity_total": modelspace_total,
        },
    }


def render_census_summary_md(summary: dict[str, Any]) -> str:
    lines = [
        "# Corpus census summary",
        "",
        f"- schema: `{summary.get('schema', '')}`",
        f"- drawings: {summary.get('totals', {}).get('drawings', 0)}",
        f"- census_ok: {summary.get('totals', {}).get('census_ok', 0)}",
        f"- modelspace_entity_total: {summary.get('totals', {}).get('modelspace_entity_total', 0)}",
        "",
        "## Per DXF",
        "",
        "| dxf_name | total_count | drawings_present | certified |",
        "| --- | ---: | ---: | --- |",
    ]
    per_dxf = summary.get("per_dxf") or {}
    for dxf_name in sorted(per_dxf):
        row = per_dxf[dxf_name]
        certified = "true" if row.get("certified") else "false"
        lines.append(
            f"| {dxf_name} | {row.get('total_count', 0)} | "
            f"{row.get('drawings_present', 0)} | {certified} |"
        )
    lines.append("")
    lines.extend(
        [
            "## Drawings",
            "",
            "| dwg | ok | modelspace_entity_total | certified_total | out_of_class_total |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for drawing in summary.get("drawings") or []:
        ok = "true" if drawing.get("ok") else "false"
        ms = drawing.get("modelspace_entity_total")
        cert = drawing.get("certified_total")
        ooc = drawing.get("out_of_class_total")
        lines.append(
            f"| {drawing.get('dwg', '')} | {ok} | "
            f"{'' if ms is None else ms} | "
            f"{'' if cert is None else cert} | "
            f"{'' if ooc is None else ooc} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_census_summary(out_root: str, summary: dict[str, Any]) -> tuple[str, str]:
    json_path = os.path.join(out_root, CENSUS_SUMMARY_JSON)
    md_path = os.path.join(out_root, CENSUS_SUMMARY_MD)
    _write_json(json_path, summary)
    Path(md_path).write_text(render_census_summary_md(summary), encoding="utf-8")
    return json_path, md_path


def run_sweep(
    plan: dict[str, Any],
    *,
    plan_only: bool = False,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    if plan_only:
        return {"entries": results}

    for entry in plan.get("entries") or []:
        cmd = list(entry.get("cmd") or [])
        returncode: int | None
        try:
            completed = subprocess.run(cmd, check=False)
            returncode = completed.returncode
        except OSError as exc:
            returncode = None
            results.append(
                {
                    "dwg": entry.get("dwg"),
                    "out_dir": entry.get("out_dir"),
                    "cmd": cmd,
                    "returncode": returncode,
                    "error": str(exc),
                }
            )
            continue
        results.append(
            {
                "dwg": entry.get("dwg"),
                "out_dir": entry.get("out_dir"),
                "cmd": cmd,
                "returncode": returncode,
            }
        )
    return {"entries": results}


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Sweep a DWG corpus through capstone census-only and aggregate."
    )
    ap.add_argument("--dwg-list", required=True, help="Text file: one absolute DWG path per line")
    ap.add_argument("--out-root", required=True, help="Output root directory")
    ap.add_argument("--plan-only", action="store_true", help="Write sweep_plan.json only; do not execute")
    ap.add_argument("--python", default=sys.executable, help="Python executable for capstone subprocess")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    out_root = os.path.abspath(args.out_root)
    os.makedirs(out_root, exist_ok=True)

    dwg_paths = load_dwg_list(args.dwg_list)
    plan = build_sweep_plan(dwg_paths, out_root, python_exe=args.python)
    _write_json(os.path.join(out_root, SWEEP_PLAN_FILE), plan)

    if args.plan_only:
        print(json.dumps({"plan": os.path.join(out_root, SWEEP_PLAN_FILE), "entries": len(plan["entries"])},
                         ensure_ascii=False))
        return 0

    sweep_results = run_sweep(plan, plan_only=False)
    _write_json(os.path.join(out_root, SWEEP_RESULTS_FILE), sweep_results)

    summary = aggregate_census(out_root)
    json_path, md_path = write_census_summary(out_root, summary)
    print(
        json.dumps(
            {
                "plan": os.path.join(out_root, SWEEP_PLAN_FILE),
                "results": os.path.join(out_root, SWEEP_RESULTS_FILE),
                "summary_json": json_path,
                "summary_md": md_path,
                "totals": summary.get("totals"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
