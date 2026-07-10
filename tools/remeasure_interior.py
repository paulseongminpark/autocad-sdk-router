#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interior remeasure runner: blockdef_diff over pinned IRs, judged against a prereg.

Formalizes the measurement-legislation remeasure pattern (R4r LEX-0008, R4s
LEX-0009): after editing the measurer, the SAME population is re-diffed and
the result is judged against a PRE-REGISTERED band, with three hard guards:

  1. population control (LEX-0006): input IR sha256 + a_def_count +
     a_entity_total must match the prereg pin exactly;
  2. name-map authenticity: the anon remap is rebuilt from the census IR via
     ir_to_patch._build_anon_remap (the production mapping), then verified
     against the baseline report's b_name rows;
  3. per-def no-regression: no definition's diff0 may drop below the
     baseline report's value (a canonicalization that un-matches previously
     matched entities is a defect, not a quotient).

Verdict vocabulary: PASS (in band, all guards green) / FAIL otherwise --
never report FAIL as PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blockdef_diff
import ir_to_patch

_INPUT_ENCODING = "utf-8-sig"
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding=_INPUT_ENCODING) as fh:
        return json.load(fh)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(_REPO_ROOT, path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census-ir", required=True)
    parser.add_argument("--post-ir", required=True)
    parser.add_argument("--baseline-report", required=True,
                        help="prior interior report: name-map verification + per-def regression baseline")
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md")
    args = parser.parse_args(argv)

    census_path = _resolve(args.census_ir)
    post_path = _resolve(args.post_ir)
    census_ir = _load_json(census_path)
    post_ir = _load_json(post_path)
    baseline = _load_json(_resolve(args.baseline_report))
    prereg = _load_json(_resolve(args.prereg))

    guards: List[Dict[str, Any]] = []

    # -- name map: production remap, verified against baseline rows
    defs_a = blockdef_diff._definitions_by_name(census_ir)
    name_map = ir_to_patch._build_anon_remap(census_ir, defs_a)
    mismatches = []
    for row in baseline.get("per_def") or []:
        if not isinstance(row, dict):
            continue
        b_name = row.get("b_name")
        if isinstance(b_name, str):
            if name_map.get(str(row.get("name"))) != b_name:
                mismatches.append(str(row.get("name")))
    guards.append({"guard": "name_map_matches_baseline",
                   "ok": not mismatches, "mismatches": mismatches[:10]})

    report = blockdef_diff.diff_block_definitions(census_ir, post_ir, name_map=name_map)
    totals = report.get("totals") or {}

    # -- population control (LEX-0006)
    pin = prereg.get("population_pin") or {}
    base_totals = (prereg.get("baseline") or {})
    pop_ok = (int(totals.get("a_def_count", -1)) == int(base_totals.get("a_def_count", -2))
              and int(totals.get("a_entity_total", -1)) == int(base_totals.get("a_entity_total", -2)))
    guards.append({"guard": "population_identity",
                   "ok": pop_ok,
                   "measured": {"a_def_count": totals.get("a_def_count"),
                                "a_entity_total": totals.get("a_entity_total")},
                   "pinned": {"a_def_count": base_totals.get("a_def_count"),
                              "a_entity_total": base_totals.get("a_entity_total")}})

    # -- per-def no-regression vs baseline
    base_by_name = {str(r.get("name")): r for r in baseline.get("per_def") or []
                    if isinstance(r, dict)}
    regressions = []
    for row in report.get("per_def") or []:
        base_row = base_by_name.get(str(row.get("name")))
        if base_row and int(row.get("diff0", 0)) < int(base_row.get("diff0", 0)):
            regressions.append({"name": row.get("name"),
                                "diff0_before": base_row.get("diff0"),
                                "diff0_after": row.get("diff0")})
    guards.append({"guard": "per_def_no_regression", "ok": not regressions,
                   "regressions": regressions})

    # -- prereg band judgment
    pred = prereg.get("prediction") or {}
    band = pred.get("band") or [None, None]
    diff0 = int(totals.get("diff0_total", -1))
    in_band = (isinstance(band, list) and len(band) == 2
               and band[0] is not None and band[1] is not None
               and int(band[0]) <= diff0 <= int(band[1]))
    guards.append({"guard": "prereg_band", "ok": in_band,
                   "band": band, "measured_diff0_total": diff0,
                   "predicted": pred.get("diff0_total")})

    verdict = "PASS" if all(g["ok"] for g in guards) else "FAIL"

    payload = {
        "schema": "ariadne.interior100.remeasure.v1",
        "verdict": verdict,
        "guards": guards,
        "inputs": {
            "census_ir": census_path,
            "census_ir_sha256": _sha256(census_path),
            "post_ir": post_path,
            "post_ir_sha256": _sha256(post_path),
            "baseline_report": _resolve(args.baseline_report),
            "prereg": _resolve(args.prereg),
        },
        "totals": totals,
        "per_def": report.get("per_def"),
        "by_kind_gap": report.get("by_kind_gap"),
    }
    _write_json(_resolve(args.out_json), payload)
    if args.out_md:
        md_path = _resolve(args.out_md)
        parent = os.path.dirname(os.path.abspath(md_path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(blockdef_diff._render_markdown(report))

    print("verdict=%s diff0=%s / %s fraction=%s band=%s"
          % (verdict, totals.get("diff0_total"), totals.get("a_entity_total"),
             totals.get("interior_diff0_fraction"), band))
    for g in guards:
        print("  guard %-28s %s" % (g["guard"], "OK" if g["ok"] else "FAIL"))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
