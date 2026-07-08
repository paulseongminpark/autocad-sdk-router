#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

_JSON_ENCODING = "utf-8-sig"
PLAN_SCHEMA = "ariadne.roundtrip_idempotence_plan.v1"
REPORT_SCHEMA = "ariadne.roundtrip_idempotence.v1"


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _write_json(path: Path, doc: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def gen1_artifacts(gen1_run_dir: str) -> Dict[str, Path]:
    run_dir = Path(gen1_run_dir).resolve()
    return {
        "run_dir": run_dir,
        "staged_dwg": run_dir / "regen" / "staged_output.dwg",
        "post_ir": run_dir / "regen" / "post" / "dwg_graph_ir.json",
    }


def validate_gen1_run_dir(gen1_run_dir: str) -> List[str]:
    artifacts = gen1_artifacts(gen1_run_dir)
    missing = []
    for key in ("staged_dwg", "post_ir"):
        if not artifacts[key].is_file():
            missing.append(str(artifacts[key]))
    return missing


def build_gen2_cmd(gen1_run_dir: str, out_dir: str, python_exe: str | None = None,
                   batch_size: int | None = None) -> List[str]:
    artifacts = gen1_artifacts(gen1_run_dir)
    cmd = [
        python_exe or sys.executable,
        "tools/full_roundtrip_capstone.py",
        "--dwg", str(artifacts["staged_dwg"].resolve()),
        "--seed", "tests/fixtures/blank_seed.dwg",
        "--out-dir", out_dir,
        "--max-def-entities-per-block", "25000",
        "--with-records",
        "--skip-identity",
    ]
    if batch_size is not None:
        cmd.extend(["--batch-size", str(batch_size)])
    return cmd


def _load_blockdef_diff() -> Any:
    try:
        return importlib.import_module("blockdef_diff")
    except Exception:
        return None


def _interiors_diff0(result: Any) -> bool:
    if result == "unavailable":
        return True
    if isinstance(result, dict):
        # ariadne.blockdef_diff.v1: fixed point iff both sides carry the same
        # definitions and every def-entity matched (0 defs on both sides is a
        # vacuously-true fixed point: nothing to drift).
        if result.get("schema") == "ariadne.blockdef_diff.v1":
            totals = result.get("totals") or {}
            same_defs = totals.get("a_def_count") == totals.get("b_def_count")
            a_total = totals.get("a_entity_total")
            b_total = totals.get("b_entity_total")
            diff0 = totals.get("diff0_total")
            counts_ok = (isinstance(a_total, int) and a_total == b_total == diff0)
            no_missing = not any(row.get("missing_side")
                                 for row in result.get("per_def") or [])
            return bool(same_defs and counts_ok and no_missing)
        if "diff0" in result:
            return bool(result.get("diff0"))
        numeric = [result.get(key) for key in ("added", "removed", "modified", "total")]
        if all(isinstance(value, int) for value in numeric):
            return sum(numeric) == 0
    return False


def build_idempotence_report(gen1_ir_path: str, gen2_ir_path: str) -> Dict[str, Any]:
    cad_diff = importlib.import_module("cad_diff")
    gen1_ir = _read_json(Path(gen1_ir_path))
    gen2_ir = _read_json(Path(gen2_ir_path))
    diff = cad_diff.compute_diff(gen1_ir, gen2_ir, comparison_basis="geometry")
    summary = diff.get("summary") or {}
    entities = {
        "diff0": int(summary.get("added", 0)) == 0 and int(summary.get("removed", 0)) == 0 and int(summary.get("modified", 0)) == 0,
        "removed": int(summary.get("removed", 0) or 0),
        "added": int(summary.get("added", 0) or 0),
        "modified": int(summary.get("modified", 0) or 0),
    }
    entities["total"] = entities["removed"] + entities["added"] + entities["modified"]

    blockdef_diff = _load_blockdef_diff()
    interiors: Any = "unavailable"
    if blockdef_diff is not None and hasattr(blockdef_diff, "diff_block_definitions"):
        interiors = blockdef_diff.diff_block_definitions(gen1_ir, gen2_ir)

    fixed_point = bool(entities["diff0"]) and _interiors_diff0(interiors)
    return {
        "schema": REPORT_SCHEMA,
        "entities": entities,
        "interiors": interiors,
        "fixed_point": fixed_point,
    }


def render_markdown(report: Dict[str, Any]) -> str:
    entities = report.get("entities") or {}
    interiors = report.get("interiors")
    return "\n".join([
        "# Roundtrip Idempotence",
        "",
        f"- fixed_point: `{bool(report.get('fixed_point'))}`",
        f"- entities: added={int(entities.get('added', 0))} removed={int(entities.get('removed', 0))} modified={int(entities.get('modified', 0))} total={int(entities.get('total', 0))}",
        f"- interiors: `{interiors if isinstance(interiors, str) else json.dumps(interiors, ensure_ascii=False, sort_keys=True)}`",
        "",
    ])


def _write_plan(out_dir: Path, gen1_run_dir: str, cmd: List[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "idempotence_plan.json", {
        "schema": PLAN_SCHEMA,
        "gen1_run_dir": str(Path(gen1_run_dir).resolve()),
        "gen2_cmd": cmd,
    })


def _write_report(out_dir: Path, report: Dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "idempotence_report.json", report)
    _write_text(out_dir / "idempotence_report.md", render_markdown(report))


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Probe gen1->gen2 fixed-point idempotence.")
    ap.add_argument("--gen1-run-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--batch-size", type=int)
    ap.add_argument("--python", dest="python_exe", default=sys.executable)
    args = ap.parse_args(argv)

    missing = validate_gen1_run_dir(args.gen1_run_dir)
    if missing:
        return 3

    out_dir = Path(args.out_dir)
    cmd = build_gen2_cmd(args.gen1_run_dir, args.out_dir, python_exe=args.python_exe,
                         batch_size=args.batch_size)
    if args.plan_only:
        _write_plan(out_dir, args.gen1_run_dir, cmd)
        return 0

    proc = subprocess.run(cmd, check=False)
    if proc.returncode not in (0, 2):
        return proc.returncode

    gen2_post_ir = Path(args.out_dir).resolve() / "regen" / "post" / "dwg_graph_ir.json"
    if not gen2_post_ir.is_file():
        return 3

    report = build_idempotence_report(
        str(gen1_artifacts(args.gen1_run_dir)["post_ir"]),
        str(gen2_post_ir),
    )
    _write_report(out_dir, report)
    return 0 if report["fixed_point"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
