#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CubiCasa5k dataset audit — pre-experiment inventory (NO detector runs).

Walks the extracted CubiCasa5k tree, parses each sample's model.svg, and
reports: parse success rate, semantic class histogram, wall polygon counts,
wall thickness distribution (short-edge length of wall quads, px), and
per-split sample counts. Output: reports/e2/ext/cubicasa_audit_v1.json (+xlsx).

Prereg note: this is dataset statistics only. Sealing of external-eval bands
(e2.wave2 amendment) happens BEFORE any detector/model is scored on this set.
"""
from __future__ import annotations

import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter

DATA = r"D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DIR = os.path.join(ROOT, "reports", "e2", "ext")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _pts(attr: str):
    vals = attr.replace(",", " ").split()
    try:
        nums = [float(v) for v in vals]
    except ValueError:
        return []
    return list(zip(nums[0::2], nums[1::2]))


def audit_svg(path: str):
    tree = ET.parse(path)
    root = tree.getroot()
    classes = Counter()
    wall_polys = 0
    wall_short_edges = []
    for el in root.iter():
        cls = el.get("class")
        if cls:
            classes[cls] += 1
        if cls and cls.split()[0] == "Wall":
            for sub in el.iter():
                if _local(sub.tag) in ("polygon", "polyline"):
                    pts = _pts(sub.get("points", ""))
                    if len(pts) < 3:
                        continue
                    wall_polys += 1
                    edges = sorted(
                        math.hypot(pts[(i + 1) % len(pts)][0] - pts[i][0],
                                   pts[(i + 1) % len(pts)][1] - pts[i][1])
                        for i in range(len(pts)))
                    if edges:
                        wall_short_edges.append(edges[0])
    return classes, wall_polys, wall_short_edges


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    splits = {}
    for split_file in ("train.txt", "val.txt", "test.txt"):
        p = os.path.join(DATA, split_file)
        if os.path.exists(p):
            ids = [ln.strip().strip("/") for ln in open(p, encoding="utf-8") if ln.strip()]
            splits[split_file.split(".")[0]] = ids

    all_classes = Counter()
    n_ok = n_fail = 0
    wall_poly_total = 0
    thick_samples = []
    per_split = {}
    fails = []
    for split, ids in splits.items():
        use = ids[:limit] if limit else ids
        s_ok = s_wall0 = 0
        for rel in use:
            svg = os.path.join(DATA, rel.replace("/", os.sep), "model.svg")
            try:
                classes, wp, edges = audit_svg(svg)
            except Exception as e:  # noqa: BLE001 — audit must survive bad files
                n_fail += 1
                if len(fails) < 20:
                    fails.append({"id": rel, "error": str(e)[:200]})
                continue
            n_ok += 1
            s_ok += 1
            all_classes.update(classes)
            wall_poly_total += wp
            if wp == 0:
                s_wall0 += 1
            thick_samples.extend(edges[:50])
        per_split[split] = {"n_listed": len(ids), "n_audited": len(use),
                            "n_ok": s_ok, "n_wall_zero": s_wall0}

    thick_samples.sort()

    def q(f):
        return round(thick_samples[int(f * (len(thick_samples) - 1))], 1) if thick_samples else None

    out = {
        "schema": "ariadne.e2_ext_cubicasa_audit.v1",
        "data_root": DATA,
        "splits": per_split,
        "parse": {"ok": n_ok, "fail": n_fail, "fail_examples": fails},
        "wall_polygons_total": wall_poly_total,
        "wall_thickness_px_quantiles": {"p05": q(.05), "p25": q(.25), "p50": q(.50),
                                        "p75": q(.75), "p95": q(.95)},
        "class_histogram_top40": dict(all_classes.most_common(40)),
        "n_classes_distinct": len(all_classes),
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    tag = f"sample{limit}" if limit else "full"
    path = os.path.join(OUT_DIR, f"cubicasa_audit_{tag}.json")
    json.dump(out, open(path, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: out[k] for k in ("splits", "parse", "wall_polygons_total",
                                          "wall_thickness_px_quantiles")}, indent=1))
    print("->", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
