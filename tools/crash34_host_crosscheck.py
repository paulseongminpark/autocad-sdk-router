#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/crash34_host_crosscheck.py -- CRASH34 x host_eligibility cross-check
(closeout follow-up F-b).

Context: the 2026-07-06 full 465-op live reachability sweep
(measure/reachable_matrix.jsonl, sweep_watchdog.ps1 -> probe_reachability.py,
classification_source=="live_probe" on every row) classified 34 ops CRASH
(status=="partial", "native job produced no parseable result JSON" on the
isolated-subprocess probe). A manual triage bucketed those 34 as
com_activex=16 / live=5 / custom-class=6 / misc=7, "believed to be honestly
headless-impossible" -- this tool checks that belief against the
op's OWN registry record (config/operations.v2.json), instead of leaving it
as an unverified belief.

Verdict logic (see classify_one docstring for the full evidentiary trail):
  * expected_crash  -- the registry record ALREADY predicts this op cannot
    run in this sweep's host (accoreconsole), via one of two unambiguous
    signals: policy.status_policy=="catalogued_not_runnable" (no wired
    dispatcher yet -- the registry's own words), or the op's own
    summary/notes text explicitly stating Core Console cannot execute it
    (verified against live.jig.point_probe's registry text verbatim).
  * anomalous_crash -- policy.status_policy=="implemented" (registry claims
    a live, wired dispatcher) AND no such textual host caveat exists. These
    are potential real bugs or registry annotation gaps -- flagged OPEN,
    never silently patched (see main()'s docstring on registry writes).

No accoreconsole/AutoCAD anywhere in this file -- pure JSON join over
already-produced sweep + registry artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.normpath(os.path.join(_THIS_DIR, ".."))

DEFAULT_MATRIX = os.path.join(_ROUTER_HOME, "measure", "reachable_matrix.jsonl")
DEFAULT_REGISTRY = os.path.join(_ROUTER_HOME, "config", "operations.v2.json")
DEFAULT_OUT_JSON = os.path.join(_ROUTER_HOME, "reports", "crash34_host_eligibility_crosscheck.json")
DEFAULT_OUT_MD = os.path.join(_ROUTER_HOME, "reports", "crash34_host_eligibility_crosscheck.md")

CRASH_CLASS = "CRASH"

VERDICT_EXPECTED = "expected_crash"
VERDICT_ANOMALOUS = "anomalous_crash"
VALID_VERDICTS = (VERDICT_EXPECTED, VERDICT_ANOMALOUS)

ACTION_NONE = "none"           # registry already correct / already documents this
ACTION_ANNOTATED = "annotated"  # this run added an unambiguous annotation (commit-trailed)
ACTION_OPEN = "open"           # ambiguous -- reported, registry left untouched
VALID_ACTIONS = (ACTION_NONE, ACTION_ANNOTATED, ACTION_OPEN)

# Substring match against the op's OWN registry summary/notes text -- the
# exact phrase found (verbatim) in live.jig.point_probe's record. Kept
# narrow and literal on purpose: this is pattern-matching an existing
# documented caveat, not inferring one.
_CORE_CONSOLE_CAVEAT = "core console can only"

# Second caveat, added by the 2026-07-06 Lane G triage of extend.customclass.
# create / extend.customobject.create: both were flagged anomalous_crash by
# this tool's own prior run (a wired dispatcher claimed, no caveat text, yet
# CRASH on both empty-arg and valid-arg probes). Lane G reproduced the SAME
# CRASH live on the canonical binary (ruling out a stale/flaky sweep row),
# then re-ran the identical op+args through tools/attended_lane.py's dedicated
# full-acad.exe lane and got created:true/errorstatus:0 on both -- proving the
# native handler (createCustomEntity/createCustomObject, AriadneNativeJob.cpp)
# is correct. Root cause: both ops' write_level.default_write_mode=="live_edit",
# and autocad-router.ps1's Action=='run' dispatch (see the
# "$effectiveWriteMode -eq 'live_edit'" branch) routes ANY op in that write
# mode to Invoke-FullAutoCadCadJob, which requires an ALREADY-OPEN AutoCAD COM
# session (GetActiveObject) -- never available to cadctl.run_operation's
# headless/isolated-subprocess callers (the reachability sweep included) --
# BEFORE it ever reaches Invoke-CadJobRoute's Core-Console dbx+crx path. This
# is a router write-mode dispatch gap, not a native code defect; see
# build_log.md's "Lane G" section for the full evidence trail.
_ATTENDED_ONLY_CAVEAT = "requires an already-open autocad session"


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8-sig") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_registry_ops(path: str) -> Dict[str, Dict[str, Any]]:
    reg = json.load(open(path, encoding="utf-8-sig"))
    return {o["id"]: o for o in reg["operations"]}


def _relpath_or_abs(path: str, start: str) -> str:
    """os.path.relpath, but falls back to an absolute path instead of raising
    when ``path``/``start`` are on different Windows drives (e.g. a tmp_path
    test fixture on C: while the router lives on D:) -- this is a display
    field only, never used for I/O."""
    try:
        return os.path.relpath(path, start).replace("\\", "/")
    except ValueError:
        return os.path.abspath(path).replace("\\", "/")


def crash_bucket(op_id: str, family: Optional[str]) -> str:
    """Reproduces the 2026-07-06 manual triage's 4 buckets (16/5/6/7) from
    op_id/family alone -- presentational grouping only, does NOT drive the
    expected/anomalous verdict (that comes from classify_one)."""
    if "custom" in op_id:
        return "custom-class"
    if family == "com_activex":
        return "com_activex"
    if family == "live":
        return "live"
    return "misc"


def classify_one(row: Dict[str, Any], op: Dict[str, Any]) -> Dict[str, Any]:
    """Classify one CRASH-class sweep row against its registry record.

    Evidence fields carried through verbatim so the report never asserts
    something the reader can't check themselves against the same two
    source files (measure/reachable_matrix.jsonl, config/operations.v2.json).
    """
    op_id = row["op_id"]
    family = op.get("family")
    status_policy = (op.get("policy") or {}).get("status_policy")
    host_eligibility = op.get("host_eligibility") or []
    engine_tier = op.get("engine_tier")
    native_api = (op.get("handler") or {}).get("native_api") or ""
    router_lane = (op.get("handler") or {}).get("router_lane")
    registry_text = "%s %s" % (op.get("summary") or "", op.get("notes") or "")

    evidence = {
        "family": family,
        "engine_tier": engine_tier,
        "host_eligibility": host_eligibility,
        "router_lane": router_lane,
        "native_api": native_api,
        "policy_status_policy": status_policy,
        "registry_summary": op.get("summary"),
        "fixture_available": row.get("fixture_available"),
        "fixture_evidence": row.get("fixture_evidence"),
        "empty_arg_reason": (row.get("empty_arg_probe") or {}).get("reason"),
    }

    if status_policy == "catalogued_not_runnable":
        return {
            "op_id": op_id, "bucket": crash_bucket(op_id, family),
            "verdict": VERDICT_EXPECTED, "registry_action": ACTION_NONE,
            "evidence": evidence,
            "reason": ("registry policy.status_policy=\"catalogued_not_runnable\" -- "
                       "the registry's own record already says no live dispatcher is "
                       "wired for this op yet; a CRASH here is not a surprise."),
        }

    if _CORE_CONSOLE_CAVEAT in registry_text.lower():
        return {
            "op_id": op_id, "bucket": crash_bucket(op_id, family),
            "verdict": VERDICT_EXPECTED, "registry_action": ACTION_NONE,
            "evidence": evidence,
            "reason": ("registry summary/notes already states Core Console cannot "
                       "execute this op (quoted in evidence.registry_summary) -- "
                       "already documented, nothing to annotate."),
        }

    if _ATTENDED_ONLY_CAVEAT in registry_text.lower():
        return {
            "op_id": op_id, "bucket": crash_bucket(op_id, family),
            "verdict": VERDICT_EXPECTED, "registry_action": ACTION_NONE,
            "evidence": evidence,
            "reason": ("registry summary/notes already documents that this op's "
                       "live_edit default write_mode routes cadctl's headless "
                       "surface to the attended full_autocad COM branch, which "
                       "an isolated/headless probe never satisfies (2026-07-06 "
                       "Lane G triage: reproduced the CRASH live, then proved "
                       "the same op+args createCustomEntity/createCustomObject "
                       "via the attended lane, created:true) -- harness "
                       "difference, not a native code defect; already "
                       "documented, nothing further to annotate."),
        }

    # policy.status_policy == "implemented" (a live, wired dispatcher is
    # claimed) and no textual host caveat found -- no registry signal
    # predicts this crash. Left OPEN, not silently patched (see main()).
    return {
        "op_id": op_id, "bucket": crash_bucket(op_id, family),
        "verdict": VERDICT_ANOMALOUS, "registry_action": ACTION_OPEN,
        "evidence": evidence,
        "reason": ("policy.status_policy==\"implemented\" (registry claims a wired, "
                   "runnable dispatcher) and no host-capability caveat exists in the "
                   "registry text -- nothing here predicts a crash; needs owner "
                   "triage, not a bot-authored registry edit."),
    }


def build_report(matrix_path: str = DEFAULT_MATRIX, registry_path: str = DEFAULT_REGISTRY
                  ) -> Dict[str, Any]:
    matrix = load_jsonl(matrix_path)
    registry = load_registry_ops(registry_path)
    crash_rows = [r for r in matrix if r.get("class") == CRASH_CLASS]

    joined: List[Dict[str, Any]] = []
    unjoined: List[str] = []
    for row in crash_rows:
        op = registry.get(row["op_id"])
        if op is None:
            unjoined.append(row["op_id"])
            continue
        joined.append(classify_one(row, op))

    verdict_counts: Dict[str, int] = {}
    bucket_counts: Dict[str, int] = {}
    action_counts: Dict[str, int] = {}
    for r in joined:
        verdict_counts[r["verdict"]] = verdict_counts.get(r["verdict"], 0) + 1
        bucket_counts[r["bucket"]] = bucket_counts.get(r["bucket"], 0) + 1
        action_counts[r["registry_action"]] = action_counts.get(r["registry_action"], 0) + 1

    return {
        "schema": "ariadne.cados.crash34_host_eligibility_crosscheck.v1",
        "source_matrix": _relpath_or_abs(matrix_path, _ROUTER_HOME),
        "source_registry": _relpath_or_abs(registry_path, _ROUTER_HOME),
        "crash_total": len(crash_rows),
        "joined_count": len(joined),
        "unjoined_op_ids": unjoined,
        "verdict_counts": verdict_counts,
        "bucket_counts": bucket_counts,
        "registry_action_counts": action_counts,
        "rows": sorted(joined, key=lambda r: (r["bucket"], r["op_id"])),
    }


def render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# CRASH-34 x host_eligibility cross-check",
        "",
        "Source: `%s` (CRASH rows) joined against `%s`."
        % (report["source_matrix"], report["source_registry"]),
        "",
        "CRASH total: %d | joined: %d | unjoined: %d"
        % (report["crash_total"], report["joined_count"], len(report["unjoined_op_ids"])),
        "Verdict counts: %s" % json.dumps(report["verdict_counts"]),
        "Bucket counts: %s" % json.dumps(report["bucket_counts"]),
        "Registry action counts: %s" % json.dumps(report["registry_action_counts"]),
        "",
        "| op_id | bucket | policy.status_policy | verdict | reason |",
        "|---|---|---|---|---|",
    ]
    for r in report["rows"]:
        reason = r["reason"].replace("|", "\\|")
        lines.append("| %s | %s | %s | %s | %s |" % (
            r["op_id"], r["bucket"], r["evidence"]["policy_status_policy"],
            r["verdict"], reason))
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", default=DEFAULT_MATRIX)
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)

    report = build_report(args.matrix, args.registry)

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write(render_markdown(report))

    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2, ensure_ascii=False))

    if report["unjoined_op_ids"]:
        print("ERROR: %d CRASH op_id(s) not found in registry: %s"
              % (len(report["unjoined_op_ids"]), report["unjoined_op_ids"]), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
