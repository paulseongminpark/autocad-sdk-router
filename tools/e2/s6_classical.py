#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S6-1 — classical ML rung (logistic + GBDT) on the frozen WSD-EVAL-v1 pack.

Prereg e2.wave2.v1:
  W2-B1: GBDT per-handle F1 >= detector v1 F1 on held-out drawings, tiers F and M.
  W2-B2: name-blind gap (report-only).
  W2-B3: anti-permutation control AUC <= 0.55.

Features come from the committed detector preds (evidence channels) plus raw
segment geometry from the embedded SEG-IR; labels from the frozen truth
ledgers. Split is deterministic: per tier, sorted drawing ids, first 70%
train / last 30% test. Seed 7 everywhere.
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEED = 7
TIERS = ("S", "F", "M")
TRAIN_FRAC = 0.7


def _layer_is_wallish(layer: str) -> bool:
    up = (layer or "").upper()
    return any(t in up for t in ("WALL", "WA", "BEARING", "벽"))


def load_tier(tier: str):
    """Return list of (drawing_id, X_full, X_nb, y, det_scores) per drawing."""
    pack = os.path.join(ROOT, "reports", "e2", "s2", "packs", tier)
    evald = os.path.join(ROOT, "reports", "e2", "s4", f"eval_{tier}")
    out = []
    for pred_path in sorted(glob.glob(os.path.join(evald, "*.full.pred.json"))):
        did = os.path.basename(pred_path).split(".")[0]
        pred = json.load(open(pred_path, encoding="utf-8"))
        truth = json.load(open(os.path.join(pack, did + ".truth.json"), encoding="utf-8"))
        wall = set(truth["wall_handles_flat"])
        per = (pred.get("scores") or {}).get("per_handle") or {}
        segs = {s.get("handle"): s for s in (pred.get("seg_ir") or {}).get("segments", [])
                if s.get("handle")}
        rows_full, rows_nb, ys, det = [], [], [], []
        for h, rec in per.items():
            ev = rec.get("evidence") or {}
            seg = segs.get(h)
            if seg is None:
                continue
            (x1, y1), (x2, y2) = seg["pts"][0], seg["pts"][-1]
            length = math.hypot(x2 - x1, y2 - y1)
            theta = math.atan2(y2 - y1, x2 - x1)
            base = [
                float(ev.get("parallel", 0.0)),
                float(ev.get("thickness", 0.0)),
                float(ev.get("junction", 0.0)),
                math.log10(length + 1.0),
                math.sin(2 * theta),
                math.cos(2 * theta),
            ]
            rows_nb.append(base)
            rows_full.append(base + [1.0 if _layer_is_wallish(seg.get("layer")) else 0.0])
            ys.append(1 if h in wall else 0)
            det.append(float(rec.get("score", 0.0)))
        out.append((did, np.array(rows_full), np.array(rows_nb),
                    np.array(ys), np.array(det)))
    return out


def prf(y_true, y_pred):
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}


def main() -> int:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    results = {"schema": "ariadne.e2_s6_classical.v1", "prereg": "e2.wave2.v1",
               "seed": SEED, "split": "per tier sorted ids, first 70% train / last 30% test",
               "tiers": {}}
    rng = np.random.default_rng(SEED)

    for tier in TIERS:
        data = load_tier(tier)
        n_train = int(len(data) * TRAIN_FRAC)
        train, test = data[:n_train], data[n_train:]

        def stack(part, idx):
            return np.concatenate([d[idx] for d in part]) if part else np.empty((0,))

        Xf_tr, Xn_tr = stack(train, 1), stack(train, 2)
        y_tr = stack(train, 3).astype(int)
        Xf_te, Xn_te = stack(test, 1), stack(test, 2)
        y_te = stack(test, 3).astype(int)
        det_te = stack(test, 4)

        tier_res = {
            "n_drawings": {"train": len(train), "test": len(test)},
            "n_handles": {"train": int(len(y_tr)), "test": int(len(y_te))},
            "wall_rate_test": round(float(y_te.mean()), 4) if len(y_te) else None,
            "detector_baseline": prf(y_te, (det_te >= 0.5).astype(int)),
        }

        arms = {}
        for arm, X_tr, X_te in (("full", Xf_tr, Xf_te), ("name_blind", Xn_tr, Xn_te)):
            models = {}
            for name, mk in (
                ("logistic", lambda: LogisticRegression(max_iter=2000, random_state=SEED)),
                ("gbdt", lambda: GradientBoostingClassifier(random_state=SEED)),
            ):
                if len(np.unique(y_tr)) < 2:
                    models[name] = "DEGENERATE_TRAIN_LABELS"
                    continue
                m = mk().fit(X_tr, y_tr)
                pred = (m.predict_proba(X_te)[:, 1] >= 0.5).astype(int)
                models[name] = prf(y_te, pred)
            arms[arm] = models
        tier_res["arms"] = arms

        # W2-B3 anti-permutation control (GBDT, full features)
        if len(np.unique(y_tr)) >= 2:
            y_perm = rng.permutation(y_tr)
            if len(np.unique(y_perm)) >= 2 and len(np.unique(y_te)) >= 2:
                mc = GradientBoostingClassifier(random_state=SEED).fit(Xf_tr, y_perm)
                auc = roc_auc_score(y_te, mc.predict_proba(Xf_te)[:, 1])
                tier_res["anti_permutation_auc"] = round(float(auc), 4)
        results["tiers"][tier] = tier_res

    # fold prereg verdicts
    def f1_of(tier, arm, model):
        rec = results["tiers"][tier]["arms"][arm].get(model)
        return rec["f1"] if isinstance(rec, dict) else None

    b1_parts = {}
    for tier in ("F", "M"):
        det_f1 = results["tiers"][tier]["detector_baseline"]["f1"]
        gb_f1 = f1_of(tier, "full", "gbdt")
        b1_parts[tier] = {"gbdt_f1": gb_f1, "detector_f1": det_f1,
                          "pass": (gb_f1 is not None and gb_f1 >= det_f1)}
    b3_aucs = {t: results["tiers"][t].get("anti_permutation_auc") for t in TIERS
               if results["tiers"][t].get("anti_permutation_auc") is not None}
    results["verdicts"] = {
        "W2-B1": {"parts": b1_parts,
                  "verdict": "PASS" if all(p["pass"] for p in b1_parts.values()) else "FAIL"},
        "W2-B2": {t: {"gap_f1": (None if f1_of(t, "full", "gbdt") is None
                                 or f1_of(t, "name_blind", "gbdt") is None
                                 else round(f1_of(t, "full", "gbdt")
                                            - f1_of(t, "name_blind", "gbdt"), 4))}
                  for t in TIERS},
        "W2-B3": {"aucs": b3_aucs,
                  "verdict": "PASS" if b3_aucs and all(a <= 0.55 for a in b3_aucs.values())
                  else "FAIL"},
    }

    outdir = os.path.join(ROOT, "reports", "e2", "s6")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "classical_v1.json")
    json.dump(results, open(out, "w", encoding="utf-8"), indent=1)

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "summary"
    ws.append(["tier", "arm", "model", "precision", "recall", "f1",
               "detector_f1", "anti_perm_auc"])
    for tier, tr in results["tiers"].items():
        for arm, models in tr["arms"].items():
            for mname, rec in models.items():
                if isinstance(rec, dict):
                    ws.append([tier, arm, mname, rec["precision"], rec["recall"],
                               rec["f1"], tr["detector_baseline"]["f1"],
                               tr.get("anti_permutation_auc")])
    wb.save(os.path.join(outdir, "classical_v1.xlsx"))

    print(json.dumps(results["verdicts"], indent=1))
    for t in TIERS:
        print(t, "detector:", results["tiers"][t]["detector_baseline"],
              "| gbdt full:", results["tiers"][t]["arms"]["full"].get("gbdt"))
    print("->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
