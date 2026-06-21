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

    sub.add_parser("status", help="read the published router status (read-only)")

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

    v = sub.add_parser("validate", help="deterministic validation gates")
    v.add_argument("--ir", required=True, help="path to a dwg_graph_ir.v1 JSON")

    reg = sub.add_parser("registry", help="operation registry views")
    reg_sub = reg.add_subparsers(dest="registry_command", required=True)
    reg_sub.add_parser("list", help="list the v2 operation registry")
    reg_sub.add_parser("coverage", help="operation coverage summary")
    reg_explain = reg_sub.add_parser("explain", help="full registry record for one operation")
    reg_explain.add_argument("op_id", help="operation id, e.g. inspect.database.graph")

    return p


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
        if args.command == "validate":
            return _emit(cad.validate(args.ir))
        if args.command == "registry":
            if args.registry_command == "list":
                return _emit(cad.registry_list())
            if args.registry_command == "coverage":
                return _emit(cad.registry_coverage())
            if args.registry_command == "explain":
                return _emit(cad.registry_explain(args.op_id))
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
