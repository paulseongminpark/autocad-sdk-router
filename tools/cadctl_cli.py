#!/usr/bin/env python
"""cadctl_cli.py -- argparse CLI for the CAD OS Layer control surface (Lane B1).

Subcommands:
  status                                  -- read the published router status (read-only)
  inspect --dwg <p> --out <dir>           -- stage a copy, extract via router, build IR
  query   --ir <ir.json> --sql "<sql>"    -- read-only SQL over the IR sqlite store
  validate --ir <ir.json>                 -- deterministic validation gates
  registry list                           -- list the v2 operation registry
  registry coverage                       -- operation coverage summary

Exit codes:
  0  on truthful success. A route/host being unavailable, or a sibling lane
     module (ir_builder/sqlite_ir_store/validator) not yet present, is reported
     truthfully and STILL exits 0 -- that is a correct, honest answer, not a
     cadctl-side failure.
  1  only on a cadctl-side failure (bad usage, an internal exception, or an
     'error' status meaning cadctl itself broke).

The JSON result is printed to stdout. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import cadctl  # noqa: E402


# Statuses that mean "cadctl itself failed" -> nonzero exit. Everything else
# (ok / blocked / unavailable / not_implemented / partial) is a truthful answer.
_CADCTL_FAILURE_STATUSES = {"error"}


def _emit(result: dict) -> int:
    print(json.dumps(result, ensure_ascii=False, indent=2))
    status = str(result.get("status", "")).lower()
    return 1 if status in _CADCTL_FAILURE_STATUSES else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cadctl",
        description="CAD OS Layer control surface (truthful router orchestrator).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    status_p = sub.add_parser("status", help="read the published router status (read-only)")
    status_p.add_argument("--json", action="store_true",
                          help="kept for operator compatibility; cadctl always emits JSON")

    insp = sub.add_parser("inspect", help="stage a copy, extract via router, build IR")
    insp.add_argument("--dwg", required=True, help="path to the input DWG (read-only original)")
    insp.add_argument("--out", required=True, help="output run directory")
    insp.add_argument("--mode", default="graph", choices=["graph", "rich"],
                      help="graph = geometry_only extract; rich = native_full database graph")
    insp.add_argument("--include-rich", dest="include_rich", action="store_true",
                      help="route native inspect.database.graph -> coverage_level=native_full IR")

    q = sub.add_parser("query", help="read-only SQL over the IR sqlite store")
    q.add_argument("--ir", required=True, help="path to a dwg_graph_ir.v1 JSON")
    q.add_argument("--sql", required=True, help="read-only SQL statement")

    ge = sub.add_parser("get-entity", help="fetch one entity by DWG handle")
    ge.add_argument("--ir", required=True, help="path to a dwg_graph_ir.v1 JSON")
    ge.add_argument("--handle", required=True, help="DWG entity handle")

    v = sub.add_parser("validate", help="deterministic validation gates")
    v.add_argument("--ir", required=True, help="path to a dwg_graph_ir.v1 JSON")

    reg = sub.add_parser("registry", help="operation registry views")
    reg_sub = reg.add_subparsers(dest="registry_command", required=True)
    reg_sub.add_parser("list", help="list the v2 operation registry")
    reg_sub.add_parser("coverage", help="operation coverage summary")
    reg_explain = reg_sub.add_parser("explain", help="full registry record for one operation")
    reg_explain.add_argument("op_id", help="operation id, e.g. inspect.database.graph")

    patch = sub.add_parser("patch", help="patch shell commands")
    patch_sub = patch.add_subparsers(dest="patch_command", required=True)
    patch_dry = patch_sub.add_parser("dry-run", help="plan a cad_patch.v1 without applying it")
    patch_dry.add_argument("--patch-json", help="inline cad_patch.v1 JSON")
    patch_dry.add_argument("--patch-file", help="path to a cad_patch.v1 JSON file")

    diff = sub.add_parser("diff", help="structural IR diff shell")
    diff.add_argument("--pre-ir", required=True, help="before dwg_graph_ir.json")
    diff.add_argument("--post-ir", required=True, help="after dwg_graph_ir.json")

    visual = sub.add_parser("visual", help="visual report shell")
    visual.add_argument("--source-ref", required=True, help="DWG/IR/source artifact path")
    visual.add_argument("--kind", default="png", help="artifact kind, e.g. png/svg/pdf/diff_overlay")
    visual.add_argument("--artifact-id", help="optional artifact id")
    visual.add_argument("--out-dir", help="optional output directory")
    visual.add_argument("--route", help="optional render route")

    live = sub.add_parser("live", help="live shell commands")
    live_sub = live.add_subparsers(dest="live_command", required=True)
    live_sub.add_parser("status", help="truthful live pump status")

    return p


def _load_patch_arg(args) -> dict:
    if args.patch_json:
        return json.loads(args.patch_json)
    if args.patch_file:
        return json.loads(Path(args.patch_file).read_text(encoding="utf-8-sig"))
    return {}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cad = cadctl.Cad()

    try:
        if args.command == "status":
            return _emit(cad.status())
        if args.command == "inspect":
            include_rich = bool(getattr(args, "include_rich", False)) or args.mode == "rich"
            return _emit(cad.inspect(args.dwg, args.out, args.mode, include_rich=include_rich))
        if args.command == "query":
            return _emit(cad.query(args.ir, args.sql))
        if args.command == "get-entity":
            return _emit(cad.get_entity(args.ir, args.handle))
        if args.command == "validate":
            return _emit(cad.validate(args.ir))
        if args.command == "registry":
            if args.registry_command == "list":
                return _emit(cad.registry_list())
            if args.registry_command == "coverage":
                return _emit(cad.registry_coverage())
            if args.registry_command == "explain":
                return _emit(cad.registry_explain(args.op_id))
        if args.command == "patch":
            if args.patch_command == "dry-run":
                return _emit(cad.patch_dry_run(_load_patch_arg(args)))
        if args.command == "diff":
            return _emit(cad.diff_before_after(args.pre_ir, args.post_ir))
        if args.command == "visual":
            return _emit(cad.visual_report(
                args.source_ref, kind=args.kind, artifact_id=args.artifact_id,
                out_dir=args.out_dir, route=args.route))
        if args.command == "live":
            if args.live_command == "status":
                return _emit(cad.live_status())
    except Exception as exc:  # genuine cadctl-side failure
        err = {
            "schema": "ariadne.cadctl.error.v1",
            "status": "error",
            "command": args.command,
            "reason": f"{type(exc).__name__}: {exc}",
        }
        print(json.dumps(err, ensure_ascii=False, indent=2))
        return 1

    parser.error("no command dispatched")
    return 2  # unreachable


if __name__ == "__main__":
    raise SystemExit(main())
