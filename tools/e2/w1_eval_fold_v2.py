#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Corrected B2 fold (verification finding VERIFY-1, 2026-07-18).

The v1 summaries (eval_{S,F,M}.json) aggregated the per-drawing `baseline`
block, whose predicted set is wall-PAIR membership (source "walls") — not the
prereg metric. The sealed metric (e2.wave1.v1 B2: "per-handle precision/recall,
threshold 0.5") lives in each eval.json's `ablation.full` block. The name-blind
summaries were vacuous duplicates because walls records ignore the layer
channel entirely.

This fold re-aggregates the committed per-drawing evals from `ablation.full`
per arm (full arm = detection with layer; name_blind arm = detection with
use_layer=False). No re-detection: preds/evals are the frozen evidence.
"""
from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fold_tier(tier: str) -> dict:
    evald = os.path.join(ROOT, "reports", "e2", "s4", f"eval_{tier}")
    out = {"tier": tier, "metric": "per-handle score >= 0.5 (eval.json ablation.full)",
           "arms": {}}
    for arm in ("full", "name_blind"):
        tp = fp = fn = 0
        n = 0
        for ep in sorted(glob.glob(os.path.join(evald, f"*.{arm}.eval.json"))):
            ev = json.load(open(ep, encoding="utf-8"))
            c = next((b for b in (ev.get("ablation") or [])
                      if b.get("channel_removed") == "none"), None)
            if c is None or not all(k in c for k in ("tp", "fp", "fn")):
                raise SystemExit(f"no ablation[channel_removed=none] counts in {ep}")
            tp += c["tp"]; fp += c["fp"]; fn += c["fn"]
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
    report = {"driver": "w1_eval_fold.v2",
              "correction": "VERIFY-1: v1 folded baseline(source=walls); v2 folds ablation.full "
                            "(prereg-faithful per-handle metric); name_blind arm now meaningful",
              "tiers": {}}
    for tier in ("S", "F", "M"):
        report["tiers"][tier] = fold_tier(tier)
    out = os.path.join(ROOT, "reports", "e2", "s4", "eval_fold_v2.json")
    json.dump(report, open(out, "w", encoding="utf-8"), indent=1)
    for tier, rec in report["tiers"].items():
        print(tier, {a: rec["arms"][a]["micro"] for a in rec["arms"]})
    print("->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
