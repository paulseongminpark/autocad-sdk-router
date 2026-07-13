#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""parallel_roundtrip_sweep: run full_roundtrip_capstone across MANY drawings
CONCURRENTLY -- one independent capstone process (hence one accoreconsole host)
per drawing, up to --workers at a time.

WHY across-drawing and not within-drawing: a single drawing's regen is ORDERED
(tools/patch_batch_planner relink ops are handle-ledger barriers -- an append's
new_handle must land in a strictly earlier batch -- and each batch mutates the
chained staged copy), so its batches cannot be parallelized naively. Different
drawings, however, are FULLY independent: separate staged copies, separate
handle ledgers, separate accoreconsole hosts. That independence is the parallel
lever for the generalization arc (test the 11 repairs + 7 LEX laws across a
corpus at once). This runner exploits exactly that and nothing unsound.

Discipline:
  - Originals stay READ-ONLY: each capstone stages its own copy (--dwg is
    "read-only; staged internally"); this runner never writes a source DWG.
  - Disk-first: parallel_sweep_summary.json is rewritten atomically after every
    drawing completes, so a killed sweep still shows exactly what finished.
  - Terminal states (octorun): success | blocked | exhausted(timeout) per
    drawing; the sweep's overall is the worst-of.
  - RAM: N concurrent accoreconsole hosts each load the AutoCAD core (heavy).
    --workers defaults CONSERVATIVELY (4). Raise it only against known free RAM
    (see memory ram_exhaustion_spawn_storm_fix: 64GB was hit twice).

Stdlib only. Passthrough args after `--` go verbatim to each capstone call, e.g.
  python tools/parallel_roundtrip_sweep.py --dwg-list corpus.txt \
      --out-root runs/gen_sweep --workers 4 -- --with-records --skip-identity
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable or "python"
CAPSTONE = os.path.join(REPO, "tools", "full_roundtrip_capstone.py")


def _slug(path):
    base = os.path.splitext(os.path.basename(path))[0]
    s = re.sub(r"[^0-9A-Za-z._-]+", "_", base).strip("_")
    return s or "drawing"


def _atomic_write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _read_json(path):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except Exception:
        return None


def _blocked_reason(summary):
    """Pull the most specific honest block reason out of a capstone summary."""
    if not isinstance(summary, dict):
        return ""
    regen = summary.get("regen") or {}
    if regen.get("apply_reason"):
        return "regen: " + str(regen["apply_reason"])[:200]
    rec = summary.get("records_regen") or {}
    if rec.get("apply_reason"):
        return "records: " + str(rec["apply_reason"])[:200]
    return str(summary.get("verdict_skipped_reason") or "")[:200]


def _run_one(dwg, out_dir, passthrough, timeout, seed):
    """Run ONE capstone subprocess for ONE drawing. Returns a result dict.
    Never raises -- a failure is reported as a terminal state, not an exception
    (so one bad drawing never aborts the sweep)."""
    os.makedirs(out_dir, exist_ok=True)
    cmd = [PY, CAPSTONE, "--dwg", dwg, "--out-dir", out_dir]
    if seed:
        cmd += ["--seed", seed]
    cmd += list(passthrough)
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    stdout_log = os.path.join(out_dir, "capstone_stdout.log")
    t0 = time.time()
    status, exit_code, note = "blocked", None, ""
    try:
        with open(stdout_log, "w", encoding="utf-8") as log:
            proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                                  cwd=REPO, env=env, timeout=timeout)
        exit_code = proc.returncode
        # exit 0 or 2 both mean the pipeline RAN, but RAN != SUCCEEDED (FM8).
        # Success requires a real verdict (roundtrip reached post-inspect and
        # produced a comparable diff). The capstone's OWN summary["status"] is
        # the authoritative terminal state: a "blocked" summary (e.g. missing
        # --batch-size) is NOT success even though summary.json exists.
        verdict = _read_json(os.path.join(out_dir, "verdict.json"))
        summary = _read_json(os.path.join(out_dir, "summary.json"))
        interior = _read_json(os.path.join(out_dir, "interior_diff.json"))
        cap_status = summary.get("status") if isinstance(summary, dict) else None
        if verdict is not None:
            status = "success"
        elif isinstance(summary, dict):
            status = "blocked"
            note = _blocked_reason(summary) or ("capstone status=%r, no verdict" % cap_status)
        else:
            status = "blocked"
            note = "no summary.json produced"
        return {
            "drawing": dwg, "out_dir": out_dir, "status": status,
            "exit_code": exit_code, "elapsed_s": round(time.time() - t0, 1),
            "capstone_status": cap_status,
            "verdict_present": verdict is not None,
            "interior_diff0_fraction": (
                (interior or {}).get("interior_diff0_fraction")
                if isinstance(interior, dict) else None),
            "note": note,
        }
    except subprocess.TimeoutExpired:
        return {"drawing": dwg, "out_dir": out_dir, "status": "exhausted",
                "exit_code": None, "elapsed_s": round(time.time() - t0, 1),
                "verdict_present": False, "note": "per-drawing timeout"}
    except Exception as exc:  # infra, not the drawing's fault
        return {"drawing": dwg, "out_dir": out_dir, "status": "blocked",
                "exit_code": None, "elapsed_s": round(time.time() - t0, 1),
                "verdict_present": False, "note": "runner exception: %r" % exc}


_RANK = {"success": 0, "exhausted": 1, "blocked": 2}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dwg-list", help="text file, one DWG path per line")
    ap.add_argument("--dwg", action="append", default=[], help="a DWG path (repeatable)")
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--workers", type=int, default=4,
                    help="max concurrent capstone/accoreconsole processes (default 4)")
    ap.add_argument("--seed", default=os.path.join("tests", "fixtures", "blank_seed.dwg"))
    ap.add_argument("--timeout-per-drawing", type=float, default=4 * 3600.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan (drawings, out-dirs, worker count) and exit; no engine")
    ap.add_argument("passthrough", nargs="*",
                    help="args after `--` forwarded verbatim to each capstone call")
    args = ap.parse_args(argv)

    dwgs = list(args.dwg)
    if args.dwg_list:
        with open(args.dwg_list, encoding="utf-8-sig") as fh:
            dwgs += [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    # de-dup, preserve order
    seen, ordered = set(), []
    for d in dwgs:
        if d not in seen:
            seen.add(d)
            ordered.append(d)
    dwgs = ordered
    if not dwgs:
        ap.error("no drawings given (use --dwg or --dwg-list)")

    missing = [d for d in dwgs if not os.path.exists(d)]
    if missing:
        ap.error("missing drawings: %s" % missing)

    os.makedirs(args.out_root, exist_ok=True)
    seed = args.seed if (args.seed and os.path.exists(os.path.join(REPO, args.seed))) else None
    passthrough = list(args.passthrough)
    # argparse leaves a leading "--" out, but be tolerant if present
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    plan = [{"drawing": d, "out_dir": os.path.join(args.out_root, "%02d_%s" % (i, _slug(d)))}
            for i, d in enumerate(dwgs)]

    print("parallel_roundtrip_sweep plan:")
    print("  drawings   : %d" % len(plan))
    print("  workers    : %d concurrent accoreconsole hosts" % args.workers)
    print("  seed       : %s" % (seed or "(none -> capstone self-stages)"))
    print("  passthrough: %s" % (" ".join(passthrough) or "(none)"))
    for p in plan:
        print("    - %s -> %s" % (os.path.basename(p["drawing"]), p["out_dir"]))
    if args.dry_run:
        print("\n[dry-run] no processes launched.")
        return 0

    summary_path = os.path.join(args.out_root, "parallel_sweep_summary.json")
    results = {}

    def _flush(overall="running"):
        _atomic_write_json(summary_path, {
            "schema": "ariadne.parallel_roundtrip_sweep.v1",
            "out_root": args.out_root, "workers": args.workers,
            "passthrough": passthrough, "drawing_count": len(plan),
            "overall": overall,
            "results": [results[p["out_dir"]] for p in plan if p["out_dir"] in results],
        })

    _flush("running")
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_run_one, p["drawing"], p["out_dir"], passthrough,
                          args.timeout_per_drawing, seed): p for p in plan}
        for fut in cf.as_completed(futs):
            res = fut.result()
            results[res["out_dir"]] = res
            print("  [done] %-40s %s (exit=%s, %ss)" % (
                os.path.basename(res["drawing"]), res["status"],
                res.get("exit_code"), res.get("elapsed_s")))
            _flush("running")

    overall = "success"
    for p in plan:
        st = results.get(p["out_dir"], {}).get("status", "blocked")
        if _RANK.get(st, 2) > _RANK.get(overall, 0):
            overall = st
    _flush(overall)
    print("\nsweep overall=%s in %ss -> %s" % (overall, round(time.time() - t0, 1), summary_path))
    return 0 if overall == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
