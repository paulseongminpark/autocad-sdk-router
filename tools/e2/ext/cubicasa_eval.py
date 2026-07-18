#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""External-track detector evaluation on CubiCasa5k SEG-IR (prereg e2.wave2.ext.v1).

Modes:
  calibrate  — val split only. Grid over scale (mm/px) x threshold; pick the
               (scale, threshold) maximizing micro-F1. Writes the frozen
               calibration to reports/e2/ext/calibration_v1.json.
  eval       — test split, SINGLE-SHOT. Loads the frozen calibration, scores
               every drawing once, folds micro/macro P/R/F1 + FP taxonomy.
               Writes reports/e2/ext/eval_test_v1.json (+xlsx evidence).

Scoring engine: fast_score from tools/e2/w1_real_defs.py — the NumPy exact
replica of evidence_grid.score() (equivalence proven in Wave 1, dev 0.00).
Layer channel is structurally empty on this track (IR neutralizes layers), so
scoring runs name-blind (use_layer False, weights renormalized). snap_tol is
held at 6 mm physical, converted to px via the candidate scale.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "e2"))
import w1_real_defs  # noqa: E402  (fast_score + evidence_grid import chain)

IR_ROOT = os.path.join(ROOT, "runs", "e2_ext_cubicasa", "ir")
REP = os.path.join(ROOT, "reports", "e2", "ext")
SCALES = (2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 15.0)   # mm per px
THRESHOLDS = (0.4, 0.5, 0.6)
SNAP_MM = 6.0


def _params(scale: float):
    return {"scale_mm_per_unit": scale, "snap_tol": SNAP_MM / scale, "use_layer": False}


def _load_split(split: str):
    d = os.path.join(IR_ROOT, split)
    out = []
    for f in sorted(glob.glob(os.path.join(d, "*.segir.json"))):
        ir = json.load(open(f, encoding="utf-8"))
        tr = json.load(open(f.replace(".segir.", ".truth."), encoding="utf-8"))
        out.append((ir["drawing_id"], ir, set(tr["wall_handles_flat"]), tr["class_of_handle"]))
    return out


def _score_split(data, scale: float):
    """Return {drawing_id: {handle: score}} for one scale."""
    prm = _params(scale)
    scored = {}
    for did, ir, _wall, _cls in data:
        res = w1_real_defs.fast_score(ir, params=prm)
        scored[did] = {h: rec["score"] for h, rec in res["per_handle"].items()}
    return scored


def _fold(data, scored, thr: float):
    tp = fp = fn = 0
    macro = []
    fp_classes = Counter()
    for did, _ir, wall, cls in data:
        ph = scored[did]
        d_tp = d_fp = d_fn = 0
        for h, sc in ph.items():
            pred = sc >= thr
            truth = h in wall
            if pred and truth:
                d_tp += 1
            elif pred:
                d_fp += 1
                fp_classes[(cls.get(h) or "(none)").split()[0]] += 1
            elif truth:
                d_fn += 1
        # truth handles that never got scored (degenerate segs) count as misses
        d_fn += len([h for h in wall if h not in ph])
        tp += d_tp
        fp += d_fp
        fn += d_fn
        p = d_tp / (d_tp + d_fp) if d_tp + d_fp else 0.0
        r = d_tp / (d_tp + d_fn) if d_tp + d_fn else 0.0
        macro.append(2 * p * r / (p + r) if p + r else 0.0)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
            "macro_f1_mean": round(sum(macro) / len(macro), 4) if macro else None,
            "fp_class_top10": dict(fp_classes.most_common(10))}


def calibrate(limit: int) -> int:
    data = _load_split("val")
    if limit:
        data = data[:limit]
    if not data:
        print("ERROR: no converted val IR found under", os.path.join(IR_ROOT, "val"))
        return 1
    grid = []
    for s in SCALES:
        scored = _score_split(data, s)
        for thr in THRESHOLDS:
            fold = _fold(data, scored, thr)
            grid.append({"scale_mm_per_px": s, "threshold": thr, **fold})
            print(f"  scale={s:5.1f} thr={thr:.1f}  P={fold['precision']:.4f} "
                  f"R={fold['recall']:.4f} F1={fold['f1']:.4f}")
    best = max(grid, key=lambda g: g["f1"])
    out = {"schema": "ariadne.e2_ext_calibration.v1", "prereg": "e2.wave2.ext.v1",
           "split": "val", "n_drawings": len(data), "limit": limit,
           "snap_mm": SNAP_MM, "grid": grid,
           "frozen": {"scale_mm_per_px": best["scale_mm_per_px"],
                      "threshold": best["threshold"], "val_f1": best["f1"]}}
    os.makedirs(REP, exist_ok=True)
    path = os.path.join(REP, "calibration_v1.json")
    json.dump(out, open(path, "w", encoding="utf-8"), indent=1)
    print("FROZEN:", json.dumps(out["frozen"]))
    print("->", path)
    return 0


def evaluate() -> int:
    cal = json.load(open(os.path.join(REP, "calibration_v1.json"), encoding="utf-8"))
    s = cal["frozen"]["scale_mm_per_px"]
    thr = cal["frozen"]["threshold"]
    data = _load_split("test")
    if not data:
        print("ERROR: no converted test IR found")
        return 1
    scored = _score_split(data, s)
    fold = _fold(data, scored, thr)
    n_zero = sum(1 for did, ir, _w, _c in data if not scored[did])
    out = {"schema": "ariadne.e2_ext_eval.v1", "prereg": "e2.wave2.ext.v1",
           "split": "test", "n_drawings": len(data),
           "calibration": cal["frozen"], "snap_mm": SNAP_MM,
           "sentinel_zero_scored_drawings": n_zero,
           "sentinel_error_rate": round(n_zero / len(data), 4),
           "detector": fold,
           "verdicts": {"EXT-B1": {"rule": "micro-F1 >= 0.60",
                                   "f1": fold["f1"],
                                   "verdict": "PASS" if fold["f1"] >= 0.60 else "FAIL"}}}
    path = os.path.join(REP, "eval_test_v1.json")
    json.dump(out, open(path, "w", encoding="utf-8"), indent=1)

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ext_test_v1"
    ws.append(["split", "n_drawings", "scale_mm_per_px", "threshold",
               "tp", "fp", "fn", "precision", "recall", "f1", "macro_f1_mean",
               "sentinel_error_rate", "EXT-B1"])
    ws.append(["test", len(data), s, thr, fold["tp"], fold["fp"], fold["fn"],
               fold["precision"], fold["recall"], fold["f1"], fold["macro_f1_mean"],
               out["sentinel_error_rate"], out["verdicts"]["EXT-B1"]["verdict"]])
    ws2 = wb.create_sheet("fp_taxonomy")
    ws2.append(["source_class", "fp_count"])
    for c, n in fold["fp_class_top10"].items():
        ws2.append([c, n])
    wb.save(os.path.join(REP, "eval_test_v1.xlsx"))
    print(json.dumps(out["verdicts"], indent=1))
    print(json.dumps({k: fold[k] for k in ("precision", "recall", "f1", "macro_f1_mean")}))
    print("->", path)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("calibrate", "eval"))
    ap.add_argument("--limit", type=int, default=0, help="calibrate: cap val drawings")
    a = ap.parse_args()
    return calibrate(a.limit) if a.mode == "calibrate" else evaluate()


if __name__ == "__main__":
    sys.exit(main())
