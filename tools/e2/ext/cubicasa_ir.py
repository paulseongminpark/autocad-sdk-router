#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CubiCasa5k model.svg -> SEG-IR converter (vector-track external truth).

Emits, per sample:
  <out>/<split>/<id>.segir.json  — detector-consumable segment IR (units px,
                                   layer neutralized to "0": no label leakage)
  <out>/<split>/<id>.truth.json  — wall_handles_flat + per-handle source class

Every polygon/polyline/line edge under the SVG Model group becomes one
segment; SVG affine transforms are accumulated down the tree. Wall truth =
elements whose nearest classed ancestor has first class token "Wall".
Non-wall geometry (furniture, windows, dimension marks, room boundaries)
stays in the IR — the scored universe contains real human-labeled negatives.

Derived data goes to runs/ (regenerable, not committed); stats to reports/.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

DATA = r"D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DEFAULT = os.path.join(ROOT, "runs", "e2_ext_cubicasa", "ir")

IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # a b c d e f


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _mat_mul(m, n):
    a1, b1, c1, d1, e1, f1 = m
    a2, b2, c2, d2, e2, f2 = n
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


_TF_RE = re.compile(r"(matrix|translate|scale|rotate)\s*\(([^)]*)\)")


def _parse_transform(attr: str):
    m = IDENT
    for kind, body in _TF_RE.findall(attr or ""):
        vals = [float(v) for v in body.replace(",", " ").split()]
        if kind == "matrix" and len(vals) == 6:
            t = tuple(vals)
        elif kind == "translate":
            tx = vals[0]
            ty = vals[1] if len(vals) > 1 else 0.0
            t = (1.0, 0.0, 0.0, 1.0, tx, ty)
        elif kind == "scale":
            sx = vals[0]
            sy = vals[1] if len(vals) > 1 else sx
            t = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif kind == "rotate":
            ang = math.radians(vals[0])
            ca, sa = math.cos(ang), math.sin(ang)
            t = (ca, sa, -sa, ca, 0.0, 0.0)
            if len(vals) == 3:
                cx, cy = vals[1], vals[2]
                t = _mat_mul(_mat_mul((1, 0, 0, 1, cx, cy), t), (1, 0, 0, 1, -cx, -cy))
        else:
            continue
        m = _mat_mul(m, t)
    return m


def _apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _pts(attr: str):
    vals = attr.replace(",", " ").split()
    try:
        nums = [float(v) for v in vals]
    except ValueError:
        return []
    return list(zip(nums[0::2], nums[1::2]))


def convert_sample(sample_dir: str):
    """Return (segments, truth_handles, class_of_handle)."""
    root = ET.parse(os.path.join(sample_dir, "model.svg")).getroot()
    segments, truth, class_of = [], [], {}
    elem_idx = 0

    def walk(el, mat, cls):
        nonlocal elem_idx
        own = el.get("class")
        if own:
            cls = own
        t = el.get("transform")
        if t:
            mat = _mat_mul(mat, _parse_transform(t))
        tag = _local(el.tag)
        pts = None
        closed = False
        if tag in ("polygon", "polyline"):
            pts = _pts(el.get("points", ""))
            closed = tag == "polygon"
        elif tag == "line":
            try:
                pts = [(float(el.get("x1", "0")), float(el.get("y1", "0"))),
                       (float(el.get("x2", "0")), float(el.get("y2", "0")))]
            except ValueError:
                pts = None
        if pts and len(pts) >= 2:
            elem_idx += 1
            world = [_apply(mat, x, y) for x, y in pts]
            n = len(world)
            n_edges = n if (closed and n >= 3) else n - 1
            first_token = (cls or "").split()[0] if cls else ""
            for i in range(n_edges):
                p1, p2 = world[i], world[(i + 1) % n]
                if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) < 1e-6:
                    continue
                h = f"e{elem_idx}_s{i}"
                segments.append({"handle": h, "layer": "0",
                                 "pts": [[round(p1[0], 3), round(p1[1], 3)],
                                         [round(p2[0], 3), round(p2[1], 3)]]})
                class_of[h] = cls or "(none)"
                if first_token == "Wall":
                    truth.append(h)
        for ch in el:
            walk(ch, mat, cls)

    walk(root, IDENT, None)
    return segments, truth, class_of


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("split", choices=("train", "val", "test"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=OUT_DEFAULT)
    a = ap.parse_args()

    ids = [ln.strip().strip("/") for ln in
           open(os.path.join(DATA, a.split + ".txt"), encoding="utf-8") if ln.strip()]
    if a.limit:
        ids = ids[: a.limit]
    outdir = os.path.join(a.out, a.split)
    os.makedirs(outdir, exist_ok=True)

    stats = []
    n_fail = 0
    for rel in ids:
        did = rel.replace("/", "_").strip("_")
        try:
            segs, truth, class_of = convert_sample(os.path.join(DATA, rel.replace("/", os.sep)))
        except Exception as e:  # noqa: BLE001 — converter must survive bad files
            n_fail += 1
            stats.append({"id": did, "error": str(e)[:200]})
            continue
        seg_ir = {"schema": "ariadne.e2_ext_segir.v1", "source": "cubicasa5k",
                  "drawing_id": did, "units": "px",
                  "segments": segs}
        json.dump(seg_ir, open(os.path.join(outdir, did + ".segir.json"), "w",
                               encoding="utf-8"))
        json.dump({"schema": "ariadne.e2_ext_truth.v1", "drawing_id": did,
                   "wall_handles_flat": truth, "class_of_handle": class_of},
                  open(os.path.join(outdir, did + ".truth.json"), "w", encoding="utf-8"))
        stats.append({"id": did, "n_segments": len(segs), "n_wall": len(truth),
                      "wall_frac": round(len(truth) / len(segs), 4) if segs else None})

    ok = [s for s in stats if "error" not in s]
    summary = {
        "schema": "ariadne.e2_ext_cubicasa_ir_summary.v1",
        "split": a.split, "n_requested": len(ids), "n_ok": len(ok), "n_fail": n_fail,
        "total_segments": sum(s["n_segments"] for s in ok),
        "total_wall_segments": sum(s["n_wall"] for s in ok),
        "wall_frac_mean": round(sum(s["wall_frac"] for s in ok if s["wall_frac"] is not None)
                                / max(1, len(ok)), 4),
        "out_dir": outdir, "samples": stats[:2000],
    }
    rep = os.path.join(ROOT, "reports", "e2", "ext")
    os.makedirs(rep, exist_ok=True)
    tag = f"{a.split}_limit{a.limit}" if a.limit else a.split
    spath = os.path.join(rep, f"cubicasa_ir_{tag}.json")
    json.dump(summary, open(spath, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: summary[k] for k in ("split", "n_ok", "n_fail",
                                              "total_segments", "total_wall_segments",
                                              "wall_frac_mean")}, indent=1))
    print("->", spath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
