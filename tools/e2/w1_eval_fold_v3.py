#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B2 fold v3 — direct per-handle fold from prediction files (the sealed metric).

Folds scores.per_handle >= threshold straight from *.{arm}.pred.json against
truth ledgers, bypassing the eval.json layer entirely (VERIFY findings 2/3:
the eval layer counted walls-pair membership, and v2's use of the eval
ablation block still mismatched the weighted name-blind arm; sol56-ultra
cross-check 2026-07-18). This is the same computation both independent
verifiers used.

Usage: python tools/e2/w1_eval_fold_v3.py --eval-prefix eval2_ --out reports/e2/s4/eval_fold_v3.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
THRESHOLD = 0.5


def fold_tier(tier: str, prefix: str) -> dict:
    evald = os.path.join(ROOT, "reports", "e2", "s4", f"{prefix}{tier}")
    pack = os.path.join(ROOT, "reports", "e2", "s2", "packs", tier)
    out = {"tier": tier, "metric": f"scores.per_handle >= {THRESHOLD} vs wall_handles_flat",
           "arms": {}}
    for arm in ("full", "name_blind"):
        tp = fp = fn = 0
        n = 0
        for pp in sorted(glob.glob(os.path.join(evald, f"*.{arm}.pred.json"))):
            did = os.path.basename(pp).split(".")[0]
            truth = set(json.load(open(os.path.join(pack, did + ".truth.json"),
                                       encoding="utf-8"))["wall_handles_flat"])
            per = (json.load(open(pp, encoding="utf-8")).get("scores") or {}).get("per_handle") or {}
            pred = {h for h, rec in per.items()
                    if isinstance(rec, dict) and float(rec.get("score", 0)) >= THRESHOLD}
            tp += len(pred & truth)
            fp += len(pred - truth)
            fn += len(truth - pred)
            n += 1
        p = tp / (tp + fp) if tp + fp else None
        r = tp / (tp + fn) if tp + fn else None
        f1 = (2 * p * r / (p + r)) if p and r else None
        out["arms"][arm] = {"n_drawings": n, "micro": {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 4) if p is not None else None,
            "recall": round(r, 4) if r is not None else None,
            "f1": round(f1, 4) if f1 is not None else None}}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-prefix", default="eval2_")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    report = {"driver": "w1_eval_fold.v3",
              "preds": f"reports/e2/s4/{a.eval_prefix}{{S,F,M}}",
              "tiers": {t: fold_tier(t, a.eval_prefix) for t in ("S", "F", "M")}}
    json.dump(report, open(os.path.join(ROOT, a.out), "w", encoding="utf-8"), indent=1)
    for tier, rec in report["tiers"].items():
        print(tier, {arm: rec["arms"][arm]["micro"] for arm in rec["arms"]})
    print("->", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
