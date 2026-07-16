#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""module_lifecycle_harness.py -- P5a lifecycle certification for module_event ops.

WHY (P5a, SDK certification ledger):
  The 16 `runtime_commands` ops reclassified as ``kind=module_event,
  dispatchable=false`` are HOST-OWNED lifecycle deliveries (kInitAppMsg /
  kUnloadAppMsg / kLoadDwgMsg / acrxEntryPoint dispatch) or forbidden loader
  mutations (acrxLoadModule / LISP load). They can never be dispatched as job
  operations -- but their UNDERLYING lifecycle demonstrably occurs on every
  clean headless job run: accoreconsole loads the .crx (kInitAppMsg -> init),
  dispatches the job (entrypoint -> handler), and exits 0 only after a clean
  unload (kUnloadAppMsg). This harness certifies that cycle INDIRECTLY, the
  only honest way to certify host-owned events without faking dispatch:

    stage fixture copy -> run ONE dispatchable op through the sanctioned probe
    path -> assert probe EXIT=0 + result status ok
    => load -> init -> dispatch -> clean unload all completed.

  It also asserts the registry contract: exactly the blocked runtime_commands
  set carries kind=module_event + dispatchable=false, and no dispatchable op
  does. (No fake PASS: if the probe cannot run, the harness FAILS -- it never
  reports lifecycle-certified without a live run.)

Usage:
    python tools/module_lifecycle_harness.py [--dwg <fixture.dwg>] [--out-dir DIR]

Exit codes: 0 = lifecycle certified; 1 = registry contract violated;
            2 = live probe failed (lifecycle NOT certified).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REGISTRY = os.path.join(_REPO, "config", "operations.v2.json")
_DEFAULT_FIXTURE = os.path.join(_REPO, "fixtures", "blank_seed.dwg")
_PROBE_OP = "inspect.runtime.capabilities"  # RUNNABLE, read-only, host-agnostic


def load_module_event_ops():
    with open(_REGISTRY, "r", encoding="utf-8-sig") as fh:
        reg = json.load(fh)
    ops = reg["operations"]
    if isinstance(ops, dict):
        ops = list(ops.values())
    module_events = [o for o in ops if o.get("kind") == "module_event"]
    dispatchable_module_events = [o for o in module_events if o.get("dispatchable") is not False]
    stray = [o["id"] for o in ops
             if o.get("dispatchable") is False and o.get("kind") != "module_event"]
    return ops, module_events, dispatchable_module_events, stray


def registry_contract_check() -> int:
    ops, module_events, bad_dispatch, stray = load_module_event_ops()
    ids = sorted(o["id"] for o in module_events)
    print(f"[registry] module_event ops: {len(module_events)}")
    for i in ids:
        print(f"  - {i}")
    ok = True
    if len(module_events) != 16:
        print(f"[registry] FAIL: expected exactly 16 module_event ops, got {len(module_events)}")
        ok = False
    if bad_dispatch:
        print(f"[registry] FAIL: module_event but dispatchable!=false: {[o['id'] for o in bad_dispatch]}")
        ok = False
    if stray:
        print(f"[registry] FAIL: dispatchable=false without kind=module_event: {stray}")
        ok = False
    non_rc = [o["id"] for o in module_events if o.get("family") != "runtime_commands"]
    if non_rc:
        print(f"[registry] FAIL: module_event outside runtime_commands: {non_rc}")
        ok = False
    return 0 if ok else 1


def live_lifecycle_probe(dwg: str, out_dir: str) -> int:
    """One sanctioned probe run == one full module lifecycle. EXIT!=0 => not certified."""
    os.makedirs(out_dir, exist_ok=True)
    staged = os.path.join(out_dir, "lifecycle_fixture.dwg")
    shutil.copyfile(dwg, staged)  # never touch the source fixture (READ-ONLY rule)
    cmd = [sys.executable, os.path.join(_REPO, "tools", "probe_reachability.py"),
           "--probe-one", _PROBE_OP, "--dwg", staged, "--out-dir", out_dir]
    print(f"[live] running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=_REPO, capture_output=True, text=True, timeout=600)
    print(proc.stdout[-2000:] if proc.stdout else "(no stdout)")
    if proc.returncode != 0:
        print(f"[live] FAIL: probe exit={proc.returncode} -- lifecycle NOT certified")
        print(proc.stderr[-1000:] if proc.stderr else "")
        return 2
    result_path = os.path.join(out_dir, "probe_result.json")
    if not os.path.isfile(result_path):
        print("[live] FAIL: probe_result.json missing -- executed != success (FM8)")
        return 2
    with open(result_path, "r", encoding="utf-8") as fh:
        payload = fh.read()
    if '"status":"ok"' not in payload.replace(" ", "") and '"status": "ok"' not in payload:
        print("[live] FAIL: probe result carries no ok status -- lifecycle NOT certified")
        return 2
    print("[live] PASS: load -> kInitAppMsg -> job dispatch -> clean unload certified"
          f" (probe {_PROBE_OP}, exit 0, result ok)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dwg", default=_DEFAULT_FIXTURE)
    ap.add_argument("--out-dir", default=os.path.join(tempfile.gettempdir(), "module_lifecycle_harness"))
    ap.add_argument("--registry-only", action="store_true",
                    help="contract check only (no live run); NEVER claims lifecycle certified")
    args = ap.parse_args()

    rc = registry_contract_check()
    if rc != 0:
        return rc
    if args.registry_only:
        print("[harness] registry contract OK (live lifecycle NOT certified in --registry-only mode)")
        return 0
    return live_lifecycle_probe(args.dwg, args.out_dir)


if __name__ == "__main__":
    sys.exit(main())
