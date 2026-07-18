#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EXT-B2 learning rung on CubiCasa SEG-IR (prereg e2.wave2.ext.v1).

Modes:
  extract <split>  — run the frozen-calibration detector once per drawing and
                     persist per-segment feature rows to runs/.../features/.
                     Features: parallel, thickness, junction (evidence channels
                     at the frozen scale), log10(len_px+1), sin2t, cos2t.
                     Label: wall truth. No layer/class feature (name-blind track).
  train            — fit HistGradientBoosting + logistic on train rows, report
                     val P/R/F1 at 0.5 proba, plus anti-permutation control
                     (EXT-B3) trained on shuffled train labels. Writes
                     reports/e2/ext/ml_val_v1.json (+xlsx). TEST IS NOT TOUCHED.

Test-split contact happens only later via a dedicated eval, one shot per rung.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools", "e2"))
sys.path.insert(0, os.path.join(ROOT, "tools", "e2", "ext"))
import w1_real_defs  # noqa: E402
import cubicasa_eval as ce  # noqa: E402

FEAT_DIR = os.path.join(ROOT, "runs", "e2_ext_cubicasa", "features")
REP = os.path.join(ROOT, "reports", "e2", "ext")
SEED = 7
FEATURE_NAMES = ("parallel", "thickness", "junction", "log10_len", "sin2t", "cos2t")


def _frozen():
    cal = json.load(open(os.path.join(REP, "calibration_v1.json"), encoding="utf-8"))
    return cal["frozen"]["scale_mm_per_px"]


def extract(split: str) -> int:
    scale = _frozen()
    prm = ce._params(scale)
    files = sorted(glob.glob(os.path.join(ce.IR_ROOT, split, "*.segir.json")))
    if not files:
        print("ERROR: no IR for split", split)
        return 1
    X_rows, y_rows, gid = [], [], []
    for gi, f in enumerate(files):
        ir = json.load(open(f, encoding="utf-8"))
        tr = json.load(open(f.replace(".segir.", ".truth."), encoding="utf-8"))
        wall = set(tr["wall_handles_flat"])
        res = w1_real_defs.fast_score(ir, params=prm)
        seg_by_h = {}
        for s in ir["segments"]:
            seg_by_h.setdefault(s["handle"], s)
        for h, rec in res["per_handle"].items():
            ev = rec["evidence"]
            s = seg_by_h.get(h)
            if s is None:
                continue
            (x1, y1), (x2, y2) = s["pts"]
            ln = math.hypot(x2 - x1, y2 - y1)
            th = math.atan2(y2 - y1, x2 - x1)
            X_rows.append((ev["parallel"], ev["thickness"], ev["junction"],
                           math.log10(ln + 1.0), math.sin(2 * th), math.cos(2 * th)))
            y_rows.append(1 if h in wall else 0)
            gid.append(gi)
        if (gi + 1) % 400 == 0:
            print(f"  extracted {gi + 1}/{len(files)}")
    os.makedirs(FEAT_DIR, exist_ok=True)
    out = os.path.join(FEAT_DIR, f"{split}.npz")
    np.savez_compressed(out,
                        X=np.asarray(X_rows, dtype=np.float32),
                        y=np.asarray(y_rows, dtype=np.int8),
                        gid=np.asarray(gid, dtype=np.int32),
                        scale=np.float64(scale))
    print(f"{split}: {len(y_rows)} rows, wall_frac={np.mean(y_rows):.4f} -> {out}")
    return 0


def _prf(y, pred):
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 4),
            "recall": round(r, 4), "f1": round(f1, 4)}


def train() -> int:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    tr = np.load(os.path.join(FEAT_DIR, "train.npz"))
    va = np.load(os.path.join(FEAT_DIR, "val.npz"))
    Xtr, ytr = tr["X"], tr["y"].astype(int)
    Xva, yva = va["X"], va["y"].astype(int)
    scale = float(tr["scale"])
    rng = np.random.default_rng(SEED)

    models = {
        "hist_gbdt": HistGradientBoostingClassifier(random_state=SEED),
        "logistic": LogisticRegression(max_iter=2000, random_state=SEED),
    }
    out = {"schema": "ariadne.e2_ext_ml_val.v1", "prereg": "e2.wave2.ext.v1",
           "scale_mm_per_px": scale, "features": list(FEATURE_NAMES), "seed": SEED,
           "n_train": int(len(ytr)), "n_val": int(len(yva)),
           "wall_frac": {"train": round(float(ytr.mean()), 4),
                         "val": round(float(yva.mean()), 4)},
           "models": {}}
    for name, m in models.items():
        m.fit(Xtr, ytr)
        proba = m.predict_proba(Xva)[:, 1]
        rec = _prf(yva, (proba >= 0.5).astype(int))
        rec["roc_auc"] = round(float(roc_auc_score(yva, proba)), 4)
        out["models"][name] = rec
        print(name, json.dumps(rec))

    # EXT-B3 anti-permutation control (hist_gbdt on shuffled train labels)
    yperm = rng.permutation(ytr)
    mc = HistGradientBoostingClassifier(random_state=SEED).fit(Xtr, yperm)
    auc = float(roc_auc_score(yva, mc.predict_proba(Xva)[:, 1]))
    out["anti_permutation_auc"] = round(auc, 4)
    out["EXT-B3_preview"] = "PASS" if auc <= 0.55 else "FAIL"
    print("anti-permutation AUC:", round(auc, 4), out["EXT-B3_preview"])

    os.makedirs(REP, exist_ok=True)
    path = os.path.join(REP, "ml_val_v1.json")
    json.dump(out, open(path, "w", encoding="utf-8"), indent=1)

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ml_val_v1"
    ws.append(["model", "split", "precision", "recall", "f1", "roc_auc",
               "n_train", "n_val", "anti_perm_auc"])
    for name, rec in out["models"].items():
        ws.append([name, "val", rec["precision"], rec["recall"], rec["f1"],
                   rec["roc_auc"], out["n_train"], out["n_val"],
                   out["anti_permutation_auc"]])
    wb.save(os.path.join(REP, "ml_val_v1.xlsx"))
    print("->", path)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    pe = sub.add_parser("extract")
    pe.add_argument("split", choices=("train", "val", "test"))
    sub.add_parser("train")
    a = ap.parse_args()
    return extract(a.split) if a.mode == "extract" else train()


if __name__ == "__main__":
    sys.exit(main())
