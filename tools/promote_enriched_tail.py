#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""promote_enriched_tail.py -- P3b tail: reprobe needs-state REACHABLE ops
against the enriched fixture and merge the fresh verdicts into a new matrix.

WHY: handle_provisioned_3.json supplies evidence-cited valid-arg fixtures for
the needs-state tail (solids/brep, xdata, ext-dict, layerstate, blockref,
region, assoc/constraint), all referencing REAL handles baked into
tests/fixtures/enriched_seed_20260716.dwg by tools/build_enriched_fixture.py.
This runner:

  1. probes each fragment op SEQUENTIALLY (concurrent probes are a proven
     false-CRASH source -- ledger P3b offset case) with probe_reachability's
     own _run_isolated + classify_op_result (same honesty gates as the sweep:
     empty-arg control leg + valid-arg fixture leg, original sha-verified);
  2. writes measure/reachable_matrix_20260716.jsonl = the 20260714 matrix with
     ONLY the reprobed rows replaced (fresh class, probe summaries, evidence),
     leaving the 20260714 artifact untouched for provenance;
  3. prints an honest promotion table (promoted / still-REACHABLE / worse).

No fake PASS: a verdict is whatever classify_op_result returns -- an op that
stays REACHABLE (or errors) is recorded that way, with the native reason.

Usage:
    python tools/promote_enriched_tail.py [--only op1,op2] [--timeout 240]
Exit 0 = ran + merged (regardless of promotion count; the matrix is the
deliverable); 1 = infrastructure failure (fixture/dwg missing, probe crash at
the harness level).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

_TOOLS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_TOOLS)
sys.path.insert(0, _TOOLS)

import probe_reachability as pr  # noqa: E402  (reuses sweep classifier verbatim)

_FRAGMENT = "handle_provisioned_3.json"
_BASE_MATRIX = os.path.join(_REPO, "measure", "reachable_matrix_20260714.jsonl")
_OUT_MATRIX = os.path.join(_REPO, "measure", "reachable_matrix_20260716.jsonl")
_RUN_DIR = os.path.join(_REPO, "runs", "p3b_tail", "promote")
_SOURCE_TAG = "p3b_tail_enriched_20260716"


def _fragment_ops() -> dict:
    out = {}
    for op_id, fx in pr.FIXTURES.items():
        if fx.get("source_fragment") == _FRAGMENT:
            out[op_id] = fx
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="comma-separated op subset")
    ap.add_argument("--timeout", type=float, default=240.0)
    args = ap.parse_args()

    ops = _fragment_ops()
    if not ops:
        print(f"[p3b] FAIL: no fixtures loaded from {_FRAGMENT}")
        return 1
    if args.only:
        wanted = {o.strip() for o in args.only.split(",") if o.strip()}
        ops = {k: v for k, v in ops.items() if k in wanted}

    base_rows, order = {}, []
    with open(_BASE_MATRIX, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            base_rows[r["op_id"]] = r
            order.append(r["op_id"])

    results = []
    for i, (op_id, fx) in enumerate(sorted(ops.items()), 1):
        dwg = os.path.join(_REPO, fx["dwg"]) if fx.get("dwg") else str(pr.DEFAULT_DWG)
        if not os.path.isfile(dwg):
            print(f"[p3b] FAIL: fixture dwg missing: {dwg}")
            return 1
        fixture = dict(fx["args"])
        if op_id == "write.entity.rasterimage" and not os.path.isabs(fixture.get("image_path", "")):
            fixture["image_path"] = os.path.join(_REPO, fixture["image_path"])
        out_dir = os.path.join(_RUN_DIR, op_id.replace(".", "_"))
        print(f"[{i:02d}/{len(ops)}] {op_id} ...", flush=True)
        payload = pr._run_isolated(op_id, dwg, out_dir, fixture, args.timeout)
        if payload.get("_original_mutated"):
            print(f"[p3b] ABORT: original mutated during {op_id}: {payload}")
            return 1
        cls = pr.classify_op_result(payload)
        old = base_rows.get(op_id, {})
        results.append((op_id, old.get("class"), cls))
        vp = cls.get("valid_arg_probe") or {}
        print(f"        {old.get('class')} -> {cls['class']}"
              + (f"  (valid: status={vp.get('status')} err={vp.get('error_code')} {str(vp.get('reason'))[:90]})"
                 if cls["class"] != "RUNNABLE" else ""))

    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    for op_id, _old, cls in results:
        row = dict(base_rows[op_id])
        row.update({
            "fixture_available": True,
            "fixture_evidence": (ops[op_id].get("evidence", "")
                                 + f" [fragment {_FRAGMENT}, dwg {ops[op_id].get('dwg')}]"),
            "class": cls["class"],
            "empty_arg_probe": cls.get("empty_arg_probe"),
            "valid_arg_probe": cls.get("valid_arg_probe"),
            "input_validated": cls.get("input_validated"),
            "classification_source": _SOURCE_TAG,
            "probed_at": now,
            "notes": (row.get("notes") or "") if isinstance(row.get("notes"), str) else "",
        })
        base_rows[op_id] = row
    with open(_OUT_MATRIX, "w", encoding="utf-8", newline="\n") as fh:
        for op_id in order:
            fh.write(json.dumps(base_rows[op_id], ensure_ascii=False) + "\n")

    import collections
    dist = collections.Counter(r["class"] for r in base_rows.values())
    promoted = [(o, a, c["class"]) for o, a, c in results
                if a == "REACHABLE" and c["class"] == "RUNNABLE"]
    still = [(o, c["class"]) for o, a, c in results if c["class"] != "RUNNABLE"]
    print(f"\n[p3b] matrix -> {os.path.relpath(_OUT_MATRIX, _REPO)}")
    print(f"[p3b] class distribution: {dict(dist)}")
    print(f"[p3b] promoted REACHABLE->RUNNABLE: {len(promoted)}")
    for o, _a, _c in promoted:
        print(f"    + {o}")
    if still:
        print(f"[p3b] not promoted ({len(still)}):")
        for o, c in still:
            print(f"    - {o}: {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
