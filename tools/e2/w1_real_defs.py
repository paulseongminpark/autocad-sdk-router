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


FAST_THRESHOLD = 4000  # above this, the O(n^2) pure-Python loop is impractical
MP_THRESHOLD = 50000   # above this, split the i-range across worker processes

_MP = {}  # worker-process globals set by _mp_init


def _mp_init(p1, p2, dv, ln, un, ang, mid, params_resolved):
    _MP.update(P1=p1, P2=p2, D=dv, L=ln, U=un, ANG=ang, MID=mid, prm=params_resolved)


def _fast_core(P1, P2, D, L, U, ANG, MID, prm, i0_range, i1_range):
    """Score i-range [i0_range, i1_range) against ALL j. Exact same block order
    and strict comparisons as the sequential path (j ascending), so results are
    bit-identical regardless of how the i-range is partitioned."""
    import numpy as np

    lo, hi = prm["_band_units"]
    atol = prm["angle_tol_deg"]
    ovmin = prm["overlap_min"]
    snap = prm["snap_tol"]
    n = len(L)
    m = i1_range - i0_range
    best_ov = np.zeros(m)
    tb_flag = np.full(m, 2, dtype=np.int8)
    tb_off = np.full(m, np.inf)
    jcount = np.zeros(m, dtype=np.int64)

    BI, BJ = 192, 8192
    eps = 1e-9
    snap2 = snap * snap
    for i0 in range(i0_range, i1_range, BI):
        i1 = min(i0 + BI, i1_range)
        bi = i1 - i0
        o0, o1 = i0 - i0_range, i1 - i0_range
        iu = U[i0:i1]
        il = L[i0:i1]
        ip1 = P1[i0:i1]
        idv = D[i0:i1]
        for j0 in range(0, n, BJ):
            j1 = min(j0 + BJ, n)
            selfmask = (np.arange(i0, i1)[:, None] == np.arange(j0, j1)[None, :])

            d = np.abs(ANG[i0:i1, None] - ANG[None, j0:j1])
            d = np.minimum(d, 180.0 - d)
            near = (d <= atol) & ~selfmask

            dx1 = P1[j0:j1, 0][None, :] - ip1[:, 0][:, None]
            dy1 = P1[j0:j1, 1][None, :] - ip1[:, 1][:, None]
            dx2 = P2[j0:j1, 0][None, :] - ip1[:, 0][:, None]
            dy2 = P2[j0:j1, 1][None, :] - ip1[:, 1][:, None]
            ta = dx1 * iu[:, 0][:, None] + dy1 * iu[:, 1][:, None]
            tb = dx2 * iu[:, 0][:, None] + dy2 * iu[:, 1][:, None]
            tlo = np.minimum(ta, tb)
            thi = np.maximum(ta, tb)
            ovlen = np.maximum(np.minimum(il[:, None], thi) - np.maximum(0.0, tlo), 0.0)
            ov = ovlen / np.minimum(il[:, None], L[j0:j1][None, :])

            mx = MID[j0:j1, 0][None, :] - ip1[:, 0][:, None]
            my = MID[j0:j1, 1][None, :] - ip1[:, 1][:, None]
            off = np.abs(mx * (-iu[:, 1][:, None]) + my * (iu[:, 0][:, None]))

            cand = near & (ov > 0.0)
            key_flag = np.where(cand & (ov >= ovmin), 0, np.where(cand, 1, 2)).astype(np.float64)
            key_off = np.where(cand, off, np.inf)
            comp = key_flag * 1e18 + key_off
            bidx = np.argmin(comp, axis=1)
            rows = np.arange(bi)
            bcomp = comp[rows, bidx]
            run_comp = tb_flag[o0:o1].astype(np.float64) * 1e18 + tb_off[o0:o1]
            upd = bcomp < run_comp
            tb_flag[o0:o1][upd] = key_flag[rows, bidx][upd].astype(np.int8)
            tb_off[o0:o1][upd] = key_off[rows, bidx][upd]

            pval = np.where(near & (ov >= ovmin) & (off >= lo) & (off <= hi), ov, 0.0)
            bmax = pval.max(axis=1)
            um = bmax > best_ov[o0:o1]
            best_ov[o0:o1][um] = bmax[um]

            wj = D[j0:j1]
            rxs = idv[:, 0][:, None] * wj[:, 1][None, :] - idv[:, 1][:, None] * wj[:, 0][None, :]
            with np.errstate(divide="ignore", invalid="ignore"):
                aP = (dx1 * wj[:, 1][None, :] - dy1 * wj[:, 0][None, :]) / rxs
                bP = (dx1 * idv[:, 1][:, None] - dy1 * idv[:, 0][:, None]) / rxs
            xj = (np.abs(rxs) >= eps) & (aP > eps) & (aP < 1.0 - eps) & (bP > eps) & (bP < 1.0 - eps)

            lj = np.zeros_like(xj)
            for A in (P1[i0:i1], P2[i0:i1]):
                for B in (P1[j0:j1], P2[j0:j1]):
                    ddx = B[:, 0][None, :] - A[:, 0][:, None]
                    ddy = B[:, 1][None, :] - A[:, 1][:, None]
                    lj |= (ddx * ddx + ddy * ddy) <= snap2

            tj = np.zeros_like(xj)
            ju = U[j0:j1]
            jl = L[j0:j1]
            for A in (P1[i0:i1], P2[i0:i1]):
                adx = A[:, 0][:, None] - P1[j0:j1, 0][None, :]
                ady = A[:, 1][:, None] - P1[j0:j1, 1][None, :]
                proj = adx * ju[:, 0][None, :] + ady * ju[:, 1][None, :]
                perp = np.abs(adx * (-ju[:, 1][None, :]) + ady * ju[:, 0][None, :])
                tj |= (proj > snap) & (proj < (jl[None, :] - snap)) & (perp <= snap)
            for B in (P1[j0:j1], P2[j0:j1]):
                bdx = B[:, 0][None, :] - ip1[:, 0][:, None]
                bdy = B[:, 1][None, :] - ip1[:, 1][:, None]
                projI = bdx * iu[:, 0][:, None] + bdy * iu[:, 1][:, None]
                perpI = np.abs(bdx * (-iu[:, 1][:, None]) + bdy * iu[:, 0][:, None])
                tj |= (projI > snap) & (projI < (il[:, None] - snap)) & (perpI <= snap)

            J = (xj | lj | tj) & ~selfmask
            jcount[o0:o1] += J.sum(axis=1)

    return best_ov, tb_flag, tb_off, jcount


def _mp_score_range(task):
    i0, i1 = task
    g = _MP
    return _fast_core(g["P1"], g["P2"], g["D"], g["L"], g["U"], g["ANG"], g["MID"],
                      g["prm"], i0, i1)


def fast_score(seg_ir, params=None) -> Dict[str, Any]:
    """NumPy-vectorized exact replica of evidence_grid.score() per_handle output.

    Replicates the reference loop's semantics including first-occurrence
    tie-breaks (argmin/argmax return first hits; cross-block updates use the
    same strict comparisons) and round-then-aggregate channel math. The
    "walls" list is NOT built (this driver never reads it). Equivalence is
    provable via --equiv-check against the reference on medium defs.
    """
    import numpy as np

    p = evidence_grid._resolve_params(seg_ir, params)
    lo, hi = p["_band_units"]
    atol = p["angle_tol_deg"]
    ovmin = p["overlap_min"]
    snap = p["snap_tol"]
    use_layer = bool(p["use_layer"])
    weights = dict(p["weights"])
    if not use_layer:
        weights["layer"] = 0.0

    recs = []
    for s in seg_ir.get("segments", []) or []:
        pts = s.get("pts") or []
        if len(pts) < 2:
            continue
        p1 = (float(pts[0][0]), float(pts[0][1]))
        p2 = (float(pts[-1][0]), float(pts[-1][1]))
        if evidence_grid._length(p1, p2) == 0.0:
            continue
        recs.append((s.get("handle") or s.get("sid"), p1, p2, s.get("layer") or ""))
    n = len(recs)
    if n == 0:
        return {"per_handle": {}, "walls": []}

    P1 = np.array([r[1] for r in recs], dtype=np.float64)
    P2 = np.array([r[2] for r in recs], dtype=np.float64)
    D = P2 - P1
    L = np.hypot(D[:, 0], D[:, 1])
    U = D / L[:, None]
    ANG = np.degrees(np.arctan2(D[:, 1], D[:, 0])) % 180.0
    MID = (P1 + P2) / 2.0
    WALLISH = np.array([evidence_grid._layer_is_wallish(r[3]) for r in recs])

    if n > MP_THRESHOLD:
        import concurrent.futures as cf
        import multiprocessing as mp

        workers = max(2, min(10, (os.cpu_count() or 4) - 2))
        chunk = (n + workers * 4 - 1) // (workers * 4)
        tasks = [(a, min(a + chunk, n)) for a in range(0, n, chunk)]
        parts = []
        with cf.ProcessPoolExecutor(
            max_workers=workers,
            mp_context=mp.get_context("spawn"),
            initializer=_mp_init,
            initargs=(P1, P2, D, L, U, ANG, MID, p),
        ) as ex:
            for task, part in zip(tasks, ex.map(_mp_score_range, tasks)):
                parts.append(part)
        best_ov = np.concatenate([pt[0] for pt in parts])
        tb_flag = np.concatenate([pt[1] for pt in parts])
        tb_off = np.concatenate([pt[2] for pt in parts])
        jcount = np.concatenate([pt[3] for pt in parts])
    else:
        best_ov, tb_flag, tb_off, jcount = _fast_core(
            P1, P2, D, L, U, ANG, MID, p, 0, n
        )

    per_handle: Dict[str, Any] = {}
    for k in range(n):
        parallel_score = float(best_ov[k])
        thickness_score = (
            evidence_grid._band_membership(float(tb_off[k]), lo, hi)
            if tb_flag[k] != 2 else 0.0
        )
        junction_score = min(1.0, jcount[k] / 2.0)
        layer_score = 1.0 if (use_layer and WALLISH[k]) else 0.0
        channels = {
            "parallel": round(parallel_score, 6),
            "thickness": round(thickness_score, 6),
            "junction": round(junction_score, 6),
            "layer": round(layer_score, 6),
        }
        wsum = sum(w for w in weights.values() if w > 0)
        agg = 0.0 if wsum <= 0 else sum(weights[c] * channels[c] for c in channels) / wsum
        per_handle[recs[k][0]] = {"score": round(agg, 6), "evidence": channels}
    return {"per_handle": per_handle, "walls": []}


def score_def(doc, units: str, block_name: str) -> Dict[str, Any]:
    segs, warnings = _block_segments(doc, block_name)
    ir = normalize._finalize(f"1.dwg#{block_name}", units, segs)
    if segs:
        if len(segs) > FAST_THRESHOLD:
            res = fast_score(ir)
            warnings = warnings + [f"fast-path n={len(segs)}"]
        else:
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
    ap.add_argument("--equiv-check", action="store_true",
                    help="prove fast_score == evidence_grid.score on medium defs, then exit")
    ap.add_argument("--mp-bench", type=int, default=0, metavar="N",
                    help="prove MP path == sequential fast path on an N-segment sample, then exit")
    args = ap.parse_args(argv)

    silver = load_silver(args.raw_dir)
    defs = sorted(silver.keys())
    print(f"def universe from top-tier silver: {len(defs)}")

    doc = ezdxf.readfile(args.dxf)
    units = normalize._units_from_doc(doc)
    print(f"staged DXF units: {units}")

    if args.mp_bench:
        import random
        import time as _time
        global MP_THRESHOLD
        segs, _w = _block_segments(doc, "X-평면도(기본형)")
        random.seed(7)
        sub = random.sample(segs, min(args.mp_bench, len(segs)))
        ir = normalize._finalize("mpbench", units, [dict(s) for s in sub])
        t0 = _time.perf_counter()
        seq = fast_score(ir)["per_handle"]
        t_seq = _time.perf_counter() - t0
        MP_THRESHOLD = max(1000, args.mp_bench // 2)
        t0 = _time.perf_counter()
        mp_res = fast_score(ir)["per_handle"]
        t_mp = _time.perf_counter() - t0
        assert set(seq) == set(mp_res), "key sets differ"
        dev = 0.0
        for k in seq:
            dev = max(dev, abs(seq[k]["score"] - mp_res[k]["score"]))
            for c in seq[k]["evidence"]:
                dev = max(dev, abs(seq[k]["evidence"][c] - mp_res[k]["evidence"][c]))
        print(f"MP_BENCH n={len(sub)} max_dev={dev:.2e} seq={t_seq:.1f}s "
              f"mp={t_mp:.1f}s speedup={t_seq / max(t_mp, 1e-9):.1f}x "
              f"-> {'PASS' if dev == 0.0 else 'FAIL'}")
        return 0 if dev == 0.0 else 1

    if args.equiv_check:
        import time as _time
        checked, max_dev = 0, 0.0
        for d in defs:
            if d not in doc.blocks:
                continue
            segs, _w = _block_segments(doc, d)
            if not (200 <= len(segs) <= FAST_THRESHOLD):
                continue
            ir = normalize._finalize(f"eq#{d}", units, segs)
            t0 = _time.perf_counter()
            ref = evidence_grid.score(ir)["per_handle"]
            t_ref = _time.perf_counter() - t0
            t0 = _time.perf_counter()
            fast = fast_score(ir)["per_handle"]
            t_fast = _time.perf_counter() - t0
            assert set(ref) == set(fast), f"{d}: key sets differ"
            dev = 0.0
            for k in ref:
                dev = max(dev, abs(ref[k]["score"] - fast[k]["score"]))
                for c in ref[k]["evidence"]:
                    dev = max(dev, abs(ref[k]["evidence"][c] - fast[k]["evidence"][c]))
            print(f"  equiv {d}: n={len(segs)} max_dev={dev:.2e} "
                  f"ref={t_ref:.2f}s fast={t_fast:.2f}s", flush=True)
            max_dev = max(max_dev, dev)
            checked += 1
            if checked >= 8:
                break
        print(f"EQUIV_CHECK defs={checked} max_dev={max_dev:.2e} "
              f"-> {'PASS' if checked and max_dev <= 1e-6 else 'FAIL'}")
        return 0 if (checked and max_dev <= 1e-6) else 1

    rows: List[Dict[str, Any]] = []
    missing: List[str] = []
    for i, d in enumerate(defs):
        if d not in doc.blocks:
            missing.append(d)
            rows.append({"def": d, "n_segments": 0, "n_scored": 0, "n_wall": 0,
                         "max_score": 0.0, "warnings": ["def-not-in-dxf"]})
        else:
            try:
                rows.append(score_def(doc, units, d))
            except Exception as exc:  # noqa: BLE001 - isolate poison defs, keep the sweep
                rows.append({"def": d, "n_segments": 0, "n_scored": 0, "n_wall": 0,
                             "max_score": 0.0,
                             "warnings": [f"score-error {type(exc).__name__}: {exc}"[:200]]})
        if (i + 1) % 16 == 0:
            print(f"  scored {i + 1}/{len(defs)} (last {d}: "
                  f"{rows[-1]['n_segments']} segs)", flush=True)

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
