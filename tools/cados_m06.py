#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CADOS M06 visual, batch, golden, performance, and review runner.

This module is intentionally stdlib-first and DWG-safe. It reads IR/DWG inputs,
uses existing staged-copy cadctl/visual/validator surfaces, and writes evidence
under an explicit run/report directory. It never writes an original DWG.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_THIS_DIR = Path(__file__).resolve().parent
_ROOT = _THIS_DIR.parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import cadctl  # noqa: E402
import validator  # noqa: E402
import visual_report  # noqa: E402

SCHEMA_VISUAL = "ariadne.cad_os.m06.visual_verification.v1"
SCHEMA_BATCH = "ariadne.cad_os.m06.batch_result.v1"
SCHEMA_GOLDEN = "ariadne.cad_os.m06.golden_regression.v1"
SCHEMA_PERF = "ariadne.cad_os.m06.performance_report.v1"
SCHEMA_REVIEW = "ariadne.cad_os.m06.review_report.v1"
_JSON_ENCODING = "utf-8-sig"


def _load_json(path: str | Path) -> Any:
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _write_json(path: str | Path, payload: Dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(p)


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _status_from_counts(successes: int, failures: int) -> str:
    if failures == 0:
        return "PASS"
    if successes > 0:
        return "PARTIAL_PASS"
    return "FAILED"


def _artifact_ref(ref: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "role": ref.get("role"),
        "ref": ref.get("ref"),
        "media_type": ref.get("media_type"),
        "byte_size": ref.get("byte_size"),
        "sha256": ref.get("sha256"),
    }


def build_visual_verification(
    before_ir: str,
    after_ir: Optional[str] = None,
    diff_ref: Optional[str] = None,
    *,
    out_dir: str,
    artifact_id: str = "m06-visual",
) -> Dict[str, Any]:
    """Render before/after/overlay SVG artifacts and write visual_verification.json."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    visual = visual_report.build_visual_report(
        before_ir,
        kind="diff_overlay" if after_ir and diff_ref else "svg",
        post_ir_path=after_ir,
        diff_path=diff_ref,
        artifact_id=artifact_id,
        out_dir=str(out),
        route="ir_svg",
    )
    artifacts = [_artifact_ref(r) for r in visual.get("refs", [])]
    visual_diff_doc = _load_json(visual["visual_diff"]) if visual.get("visual_diff") else {}
    handles = visual_diff_doc.get("highlighted_handles") or []
    status = "PASS" if visual.get("status") == "ok" else visual.get("status", "FAILED").upper()
    result = {
        "schema": SCHEMA_VISUAL,
        "status": status,
        "render_status": visual.get("status"),
        "route": visual.get("route"),
        "source_before_ir": before_ir,
        "source_after_ir": after_ir,
        "diff_ref": diff_ref,
        "run_dir": str(out),
        "artifacts": artifacts,
        "visual_artifact": visual,
        "visual_diff": visual.get("visual_diff"),
        "viewport_metadata": {
            "before": (visual.get("diagnostics") or {}).get("before", {}).get("viewbox"),
            "after": (visual.get("diagnostics") or {}).get("after", {}).get("viewbox"),
            "overlay": (visual.get("diagnostics") or {}).get("overlay", {}).get("viewbox"),
        },
        "handles_highlighted": sorted(handles),
        "diagnostics": visual.get("diagnostics", {}),
    }
    _write_json(out / "visual_verification.json", result)
    return result


def _validate_ir_fixture(fixture: Dict[str, Any], out: Path) -> Dict[str, Any]:
    fid = str(fixture.get("id", "fixture"))
    ir_path = str(fixture.get("ir_path", ""))
    if not ir_path or not Path(ir_path).is_file():
        return {"id": fid, "kind": "ir_validate", "status": "FAILED",
                "reason": "ir_path not found", "ir_path": ir_path}
    t0 = _now_ms()
    report = validator.validate_target(ir_path=ir_path)
    elapsed = round(_now_ms() - t0, 3)
    ref = out / f"{fid}_validation.json"
    _write_json(ref, report)
    status = "PASS" if report.get("status") == "pass" else "FAILED"
    return {"id": fid, "kind": "ir_validate", "status": status, "ir_path": ir_path,
            "validation_ref": str(ref), "duration_ms": elapsed,
            "gates_total": report.get("summary", {}).get("gates_total"),
            "gates_failed": report.get("summary", {}).get("gates_failed")}


def _inspect_dwg_fixture(fixture: Dict[str, Any], out: Path) -> Dict[str, Any]:
    fid = str(fixture.get("id", "fixture"))
    dwg_path = str(fixture.get("dwg_path", ""))
    if not dwg_path or not Path(dwg_path).is_file():
        return {"id": fid, "kind": "dwg_inspect_validate", "status": "FAILED",
                "reason": "dwg_path not found", "dwg_path": dwg_path}
    t0 = _now_ms()
    run_dir = out / fid
    result = cadctl.Cad().inspect(dwg_path, str(run_dir), "rich", include_rich=True)
    elapsed = round(_now_ms() - t0, 3)
    _write_json(run_dir / "inspect_result.json", result)
    ir_ref = result.get("ir_ref") or str(run_dir / "dwg_graph_ir.json")
    if result.get("status") != "ok" or not Path(ir_ref).is_file():
        return {"id": fid, "kind": "dwg_inspect_validate", "status": "FAILED",
                "dwg_path": dwg_path, "inspect_ref": str(run_dir / "inspect_result.json"),
                "duration_ms": elapsed, "reason": result.get("reason") or result.get("status")}
    report = validator.validate_target(ir_path=ir_ref, run_dir=str(run_dir))
    validation_ref = run_dir / "validation.json"
    _write_json(validation_ref, report)
    status = "PASS" if report.get("status") == "pass" else "FAILED"
    return {"id": fid, "kind": "dwg_inspect_validate", "status": status,
            "dwg_path": dwg_path, "inspect_ref": str(run_dir / "inspect_result.json"),
            "ir_ref": ir_ref, "validation_ref": str(validation_ref),
            "duration_ms": elapsed, "entity_count": result.get("entity_count")}


def run_batch_manifest(manifest_path: str, *, out_dir: str) -> Dict[str, Any]:
    """Run sequential fixture validation/inspect jobs with failure isolation."""
    manifest = _load_json(manifest_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    quarantine: List[Dict[str, Any]] = []
    for fixture in manifest.get("fixtures", []) or []:
        kind = fixture.get("kind", "ir_validate")
        if kind == "ir_validate":
            rec = _validate_ir_fixture(fixture, out)
        elif kind == "dwg_inspect_validate":
            rec = _inspect_dwg_fixture(fixture, out)
        else:
            rec = {"id": fixture.get("id", "fixture"), "kind": kind,
                   "status": "FAILED", "reason": f"unsupported fixture kind: {kind}"}
        results.append(rec)
        if rec.get("status") != "PASS":
            quarantine.append({"id": rec.get("id"), "kind": rec.get("kind"),
                               "reason": rec.get("reason", "fixture failed")})
    successes = sum(1 for r in results if r.get("status") == "PASS")
    failures = len(results) - successes
    payload = {
        "schema": SCHEMA_BATCH,
        "status": _status_from_counts(successes, failures),
        "manifest": manifest_path,
        "out_dir": str(out),
        "successes": successes,
        "failures": failures,
        "results": results,
        "quarantine": quarantine,
    }
    _write_json(out / "batch_summary.json", payload)
    return payload


def _entity_counts(ir: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for ent in ir.get("entities", []) or []:
        if isinstance(ent, dict):
            key = str(ent.get("dxf_name") or ent.get("class") or "UNKNOWN")
            counts[key] = counts.get(key, 0) + 1
    return counts


def run_golden_regression(manifest_path: str, expected_counts_path: str, *, out_dir: str) -> Dict[str, Any]:
    """Compare golden fixture IR counts against expected_counts.json."""
    manifest = _load_json(manifest_path)
    expected = _load_json(expected_counts_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fixture_defs = manifest.get("fixtures")
    if not isinstance(fixture_defs, list):
        fixture_defs = [{"id": "golden", "ir_path": manifest.get("native_full_ir", {}).get("path")}]
    fixtures = []
    for fixture in fixture_defs:
        fid = str(fixture.get("id", "golden"))
        ir_path = fixture.get("ir_path")
        if not ir_path:
            ir_path = manifest.get("native_full_ir", {}).get("path")
        if ir_path and not Path(ir_path).is_absolute():
            ir_path = str((_ROOT / ir_path).resolve())
        if not ir_path or not Path(ir_path).is_file():
            fixtures.append({"id": fid, "status": "FAILED", "reason": "ir_path not found",
                             "ir_path": ir_path})
            continue
        ir = _load_json(ir_path)
        counts = _entity_counts(ir)
        entity_count = len(ir.get("entities", []) or [])
        expected_total = expected.get("modelspace_total")
        expected_by_type = expected.get("by_type", {}) or {}
        mismatches = []
        if isinstance(expected_total, int) and entity_count != expected_total:
            mismatches.append(f"entity_count {entity_count} != expected {expected_total}")
        for key, value in expected_by_type.items():
            if counts.get(key, 0) != value:
                mismatches.append(f"{key} {counts.get(key, 0)} != expected {value}")
        fixtures.append({"id": fid, "status": "PASS" if not mismatches else "FAILED",
                         "ir_path": ir_path, "entity_count": entity_count,
                         "by_type": counts, "mismatches": mismatches})
    failures = sum(1 for f in fixtures if f.get("status") != "PASS")
    payload = {
        "schema": SCHEMA_GOLDEN,
        "status": "PASS" if failures == 0 else "FAILED",
        "manifest": manifest_path,
        "expected_counts": expected_counts_path,
        "fixtures": fixtures,
    }
    _write_json(out / "golden_regression.json", payload)
    return payload


def build_performance_report(
    artifacts: Iterable[Dict[str, Any]],
    *,
    out_dir: str,
    thresholds: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Record deterministic parse/size timing for artifacts."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    thresholds = thresholds or {}
    records = []
    for artifact in artifacts:
        aid = str(artifact.get("id", "artifact"))
        path = str(artifact.get("path", ""))
        t0 = _now_ms()
        byte_size = Path(path).stat().st_size if path and Path(path).is_file() else 0
        entity_count = None
        status = "PASS"
        reason = ""
        if not byte_size:
            status = "FAILED"
            reason = "path not found or empty"
        elif artifact.get("kind") == "ir":
            doc = _load_json(path)
            entity_count = len(doc.get("entities", []) or []) if isinstance(doc, dict) else None
        duration_ms = round(_now_ms() - t0, 3)
        limit = (thresholds.get(aid) or {}).get("max_duration_ms")
        if isinstance(limit, (int, float)) and duration_ms > float(limit):
            status = "FAILED"
            reason = f"duration_ms {duration_ms} > threshold {limit}"
        records.append({"id": aid, "kind": artifact.get("kind"), "path": path,
                        "status": status, "reason": reason,
                        "duration_ms": duration_ms, "byte_size": byte_size,
                        "entity_count": entity_count})
    payload = {
        "schema": SCHEMA_PERF,
        "status": "PASS" if all(r["status"] == "PASS" for r in records) else "FAILED",
        "artifacts": records,
        "thresholds": thresholds,
    }
    _write_json(out / "performance_report.json", payload)
    return payload


def build_review_report(summary: Dict[str, Any], *, out_dir: str) -> Dict[str, Any]:
    """Write static Markdown and HTML review report."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = out / "review_report.md"
    html_ref = out / "review_report.html"
    lines = [
        "# CADOS M06 Review Report",
        "",
        "## Visual",
        f"- status: {summary.get('visual', {}).get('status')}",
        "",
        "## Batch",
        f"- status: {summary.get('batch', {}).get('status')}",
        f"- successes: {summary.get('batch', {}).get('successes')}",
        f"- failures: {summary.get('batch', {}).get('failures')}",
        "",
        "## Golden",
        f"- status: {summary.get('golden', {}).get('status')}",
        "",
        "## Performance",
        f"- status: {summary.get('performance', {}).get('status')}",
    ]
    for artifact in summary.get("visual", {}).get("artifacts", []) or []:
        lines.append(f"- visual {artifact.get('role')}: `{artifact.get('ref')}`")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    html_body = "\n".join(f"<p>{html.escape(line)}</p>" if line else "" for line in lines)
    html_ref.write_text("<!doctype html><meta charset=\"utf-8\"><title>CADOS M06</title>\n"
                        + html_body + "\n", encoding="utf-8")
    payload = {"schema": SCHEMA_REVIEW, "status": "PASS",
               "markdown_ref": str(md), "html_ref": str(html_ref)}
    _write_json(out / "review_report.json", payload)
    return payload


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="cados_m06.py")
    sub = parser.add_subparsers(dest="command", required=True)
    visual = sub.add_parser("visual")
    visual.add_argument("--before", required=True)
    visual.add_argument("--after")
    visual.add_argument("--diff")
    visual.add_argument("--out", required=True)
    batch = sub.add_parser("batch")
    batch.add_argument("--manifest", required=True)
    batch.add_argument("--out", required=True)
    golden = sub.add_parser("golden")
    golden.add_argument("--manifest", required=True)
    golden.add_argument("--expected", required=True)
    golden.add_argument("--out", required=True)
    perf = sub.add_parser("perf")
    perf.add_argument("--artifact", action="append", default=[],
                      help="id:kind:path")
    perf.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "visual":
        result = build_visual_verification(args.before, args.after, args.diff, out_dir=args.out)
    elif args.command == "batch":
        result = run_batch_manifest(args.manifest, out_dir=args.out)
    elif args.command == "golden":
        result = run_golden_regression(args.manifest, args.expected, out_dir=args.out)
    elif args.command == "perf":
        artifacts = []
        for raw in args.artifact:
            aid, kind, path = raw.split(":", 2)
            artifacts.append({"id": aid, "kind": kind, "path": path})
        result = build_performance_report(artifacts, out_dir=args.out)
    else:  # pragma: no cover
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in ("PASS", "PARTIAL_PASS") else 1


if __name__ == "__main__":
    raise SystemExit(_main())
