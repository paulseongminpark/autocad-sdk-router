#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wave-1 B3/B5 driver: per-def detector scoring on the staged DXF of 1.dwg.

B3 (banded, prereg e2.wave1.v1): zero_frac_v1 = share of the 384 E1 defs where
detector v1 scores zero wall handles (score >= 0.5), vs v0 baseline 0.682.
B5 (exploratory, no band): Pearson(per-def max score, E1.5 top-tier mean
wall_likelihood, merged-vocab silver).

The input DXF must be a STAGED derivative produced through the CAD-OS lane
(transform.database.dxf_out); originals stay READ-ONLY. ezdxf here reads that
staged copy only, via the same injected-module pattern as detect/cli.py.

Usage:
  python tools/e2/w1_real_defs.py --dxf runs/e2_b3_dxfout_20260717/1_export.dxf \
      --raw-dir reports/e1/annot_v1/raw --out-json reports/e2/s4/real_defs_v1.json \
      --out-xlsx reports/e2/s4/real_defs_v1.xlsx
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_DETECT = os.path.join(_HERE, "detect")

TOP_TIER = ["opus48_max", "fable5_high", "sol56_xhigh"]  # tools/e15_collect.py
V0_ZERO_FRAC = 0.682  # calibration_v0.json handle_jaccard.zero_frac (prereg B3)
BAND_ZERO_FRAC = 0.40
WALL_THRESHOLD = 0.5
MAX_DEPTH = 16


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


normalize = _load("e2_normalize", os.path.join(_DETECT, "normalize.py"))
insert_expand = _load("e2_insert_expand", os.path.join(_DETECT, "insert_expand.py"))
evidence_grid = _load("e2_evidence_grid", os.path.join(_DETECT, "evidence_grid.py"))

import ezdxf  # noqa: E402  (read staged copy only)


# --------------------------------------------------------------------------- #
# silver (E1.5 top-tier mean wall_likelihood)
# --------------------------------------------------------------------------- #
def load_silver(raw_dir: str) -> Dict[str, Dict[str, Any]]:
    """def name -> {judges: {id: likelihood}, mean: float}."""
    acc: Dict[str, Dict[str, float]] = {}
    for judge in TOP_TIER:
        for shard in sorted(glob.glob(os.path.join(raw_dir, judge, "*.json"))):
            data = json.load(open(shard, encoding="utf-8"))
            records = data if isinstance(data, list) else data.get("answers") or []
            for rec in records:
                d = rec.get("def")
                wl = rec.get("wall_likelihood")
                if d is None or wl is None:
                    continue
                acc.setdefault(d, {})[judge] = float(wl)
    out: Dict[str, Dict[str, Any]] = {}
    for d, judges in acc.items():
        out[d] = {"judges": judges, "mean": sum(judges.values()) / len(judges)}
    return out


# --------------------------------------------------------------------------- #
# per-def SEG-IR assembly (block-local coords; nested INSERTs expanded)
# --------------------------------------------------------------------------- #
def _block_segments(doc, block_name: str) -> Tuple[List[dict], List[str]]:
    """Flatten a block definition into SEG-IR segments; returns (segs, warnings)."""
    warnings: List[str] = []

    def walk(name: str, xform, stack: List[str], depth: int) -> List[dict]:
        if depth > MAX_DEPTH:
            warnings.append(f"depth-cap at {name}")
            return []
        if name in stack:
            warnings.append(f"cycle at {name}")
            return []
        try:
            block = doc.blocks[name]
        except (KeyError, ezdxf.DXFError):
            warnings.append(f"missing-block {name}")
            return []
        segs: List[dict] = []
        for e in block:
            if e.dxftype() == "INSERT":
                base = insert_expand._base_point(
                    doc.blocks.get(e.dxf.name) if e.dxf.name in doc.blocks else None
                ) if e.dxf.name in doc.blocks else (0.0, 0.0)
                child = insert_expand._insert_matrix(e, base)
                composed = child if xform is None else insert_expand._compose(xform, child)
                segs.extend(walk(e.dxf.name, composed, stack + [name], depth + 1))
            else:
                contract = None if xform is None else insert_expand._to_contract(xform)
                try:
                    segs.extend(normalize.entity_to_segments(e, transform=contract))
                except Exception as exc:  # noqa: BLE001 - per-entity isolation
                    warnings.append(f"entity {e.dxftype()} {exc}")
        return segs

    return walk(block_name, None, [], 1), warnings


def score_def(doc, units: str, block_name: str) -> Dict[str, Any]:
    segs, warnings = _block_segments(doc, block_name)
    ir = normalize._finalize(f"1.dwg#{block_name}", units, segs)
    if segs:
        res = evidence_grid.score(ir)
        per = res.get("per_handle") or {}
        scores = [float(v.get("score", 0.0)) for v in per.values()]
        n_wall = sum(1 for s in scores if s >= WALL_THRESHOLD)
        max_score = max(scores) if scores else 0.0
    else:
        per, n_wall, max_score = {}, 0, 0.0
    return {
        "def": block_name,
        "n_segments": len(segs),
        "n_scored": len(per),
        "n_wall": n_wall,
        "max_score": round(max_score, 6),
        "warnings": warnings[:4],
    }


def pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Wave-1 B3/B5 per-def real-drawing eval")
    ap.add_argument("--dxf", required=True, help="staged DXF (CAD-OS derived copy)")
    ap.add_argument("--raw-dir", required=True, help="E1.5 raw judge dir")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-xlsx", required=True)
    args = ap.parse_args(argv)

    silver = load_silver(args.raw_dir)
    defs = sorted(silver.keys())
    print(f"def universe from top-tier silver: {len(defs)}")

    doc = ezdxf.readfile(args.dxf)
    units = normalize._units_from_doc(doc)
    print(f"staged DXF units: {units}")

    rows: List[Dict[str, Any]] = []
    missing: List[str] = []
    for i, d in enumerate(defs):
        if d not in doc.blocks:
            missing.append(d)
            rows.append({"def": d, "n_segments": 0, "n_scored": 0, "n_wall": 0,
                         "max_score": 0.0, "warnings": ["def-not-in-dxf"]})
        else:
            rows.append(score_def(doc, units, d))
        if (i + 1) % 64 == 0:
            print(f"  scored {i + 1}/{len(defs)}")

    for r in rows:
        r["silver_mean_wall_likelihood"] = round(silver[r["def"]]["mean"], 4)

    n = len(rows)
    zero_wall = [r for r in rows if r["n_wall"] == 0]
    zero_scored = [r for r in rows if r["n_scored"] == 0]
    zero_frac_v1 = len(zero_wall) / n if n else None
    zero_scored_frac = len(zero_scored) / n if n else None

    xs = [r["max_score"] for r in rows]
    ys = [r["silver_mean_wall_likelihood"] for r in rows]
    r_all = pearson(xs, ys)
    nz = [(r["max_score"], r["silver_mean_wall_likelihood"])
          for r in rows if r["n_segments"] > 0]
    r_nonempty = pearson([a for a, _ in nz], [b for _, b in nz]) if nz else None

    verdict = "PASS" if (zero_frac_v1 is not None and zero_frac_v1 <= BAND_ZERO_FRAC) else "FAIL"
    summary = {
        "schema": "ariadne.e2_real_defs.v1",
        "prereg": "e2.wave1.v1",
        "dxf": args.dxf,
        "units": units,
        "n_defs": n,
        "n_missing_in_dxf": len(missing),
        "missing_defs": missing[:20],
        "B3": {
            "zero_frac_v1": round(zero_frac_v1, 4) if zero_frac_v1 is not None else None,
            "zero_scored_frac": round(zero_scored_frac, 4) if zero_scored_frac is not None else None,
            "v0_baseline": V0_ZERO_FRAC,
            "band": f"<= {BAND_ZERO_FRAC}",
            "verdict": verdict,
            "note": "missing-in-dxf defs count as zero (conservative strict reading)",
        },
        "B5": {
            "pearson_all_defs": round(r_all, 4) if r_all is not None else None,
            "pearson_nonempty_defs": round(r_nonempty, 4) if r_nonempty is not None else None,
            "n_nonempty": len(nz),
            "top_tier": TOP_TIER,
            "verdict": "REPORT_ONLY",
        },
    }

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    json.dump({"summary": summary, "rows": rows},
              open(args.out_json, "w", encoding="utf-8"), indent=1)

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "per_def"
    headers = ["def", "n_segments", "n_scored", "n_wall", "max_score",
               "silver_mean_wall_likelihood", "warnings"]
    ws.append(headers)
    for r in rows:
        ws.append([r["def"], r["n_segments"], r["n_scored"], r["n_wall"],
                   r["max_score"], r["silver_mean_wall_likelihood"],
                   "; ".join(r["warnings"])])
    ws2 = wb.create_sheet("summary")
    for k, v in [("n_defs", n), ("n_missing_in_dxf", len(missing)),
                 ("zero_frac_v1", summary["B3"]["zero_frac_v1"]),
                 ("zero_scored_frac", summary["B3"]["zero_scored_frac"]),
                 ("v0_baseline", V0_ZERO_FRAC), ("B3_verdict", verdict),
                 ("pearson_all_defs", summary["B5"]["pearson_all_defs"]),
                 ("pearson_nonempty_defs", summary["B5"]["pearson_nonempty_defs"]),
                 ("n_nonempty", len(nz))]:
        ws2.append([k, v])
    wb.save(args.out_xlsx)

    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
