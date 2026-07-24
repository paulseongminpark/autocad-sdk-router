#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M-15 deterministic_v1 -- rule-based wall detector + T-META v1 invariance measure.

Step 2 (implementation) + Step 3 (measurement) of the sealed procedure.
- Loads the SEALED rule spec (PREREG_local.json), re-verifies spec_sha256.
- Implements deterministic_v1 exactly as sealed (parallel-band pairing + length gate).
- Measures R-META (drawing-macro violation rate) for the MEASURABLE cells
  F01 translate, F02 rotate, F03 uniform-scale, F07 coord-jitter on val-A DEV.
- F04/F05/F06 are BLOCKED_INPUT (substrate absent) -- recorded, never vacuous-passed.
- No v0 number consulted. No threshold re-search. CPU only.
"""
from __future__ import annotations
import csv
import ctypes
import hashlib
import json
import math
import platform
import sys
import time
from ctypes import wintypes
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

CELL = Path(__file__).resolve().parent
IR_VAL = Path(r"D:\dev\99_tools\autocad-sdk-router\runs\e2_ext_cubicasa\ir\val")
MANIFEST = Path(r"D:\runs\e2_program\cells\w2_09_valb\split_manifest.json")


# ---- Windows peak working set (peak_rss) ----------------------------------
class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


_K32 = ctypes.windll.kernel32
_PSAPI = ctypes.windll.psapi
_K32.GetCurrentProcess.restype = wintypes.HANDLE
_PSAPI.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
_PSAPI.GetProcessMemoryInfo.restype = wintypes.BOOL


def peak_rss_bytes() -> int:
    c = _PMC(); c.cb = ctypes.sizeof(c)
    ok = _PSAPI.GetProcessMemoryInfo(_K32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return int(c.PeakWorkingSetSize) if ok else -1


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# ---- Load + verify sealed spec --------------------------------------------
PREREG = json.loads((CELL / "PREREG_local.json").read_text(encoding="utf-8"))
_recomputed = sha256_bytes(canonical(PREREG["rule_specification"]))
assert _recomputed == PREREG["spec_sha256"], (
    f"SPEC SEAL MISMATCH: {_recomputed} != {PREREG['spec_sha256']}")
SPEC = PREREG["rule_specification"]
R1 = SPEC["rules"]["R1_parallel_band_pairing"]
ANGLE_TOL = math.radians(float(R1["angle_tol_deg"]))
GAP_MIN = float(R1["gap_min_px"]); GAP_MAX = float(R1["gap_max_px"])
OVERLAP_FRAC = float(R1["overlap_min_frac"])
LEN_MIN = float(SPEC["rules"]["R2_length_gate"]["len_min_px"])
RECALL_FLOOR = float(SPEC["sentinel_qualification"]["positive_recall_floor"])
NEAR_ALL = float(SPEC["sentinel_qualification"]["near_all_thresh"])
CODE_SHA = sha256_bytes(Path(__file__).read_bytes())


# ---- Geometry loader -------------------------------------------------------
def load_drawing(did: str):
    ir = json.loads((IR_VAL / f"{did}.segir.json").read_text(encoding="utf-8"))
    tr = json.loads((IR_VAL / f"{did}.truth.json").read_text(encoding="utf-8"))
    handles, p1, p2 = [], [], []
    for seg in ir.get("segments", []) or []:
        pts = seg.get("pts") or []
        if len(pts) < 2:
            continue
        a = (float(pts[0][0]), float(pts[0][1]))
        b = (float(pts[-1][0]), float(pts[-1][1]))
        if a[0] == b[0] and a[1] == b[1]:
            continue
        handles.append(str(seg.get("handle") or seg.get("sid")))
        p1.append(a); p2.append(b)
    P1 = np.asarray(p1, dtype=np.float64).reshape(-1, 2)
    P2 = np.asarray(p2, dtype=np.float64).reshape(-1, 2)
    walls = set(tr.get("wall_handles_flat") or [])
    y = np.array([h in walls for h in handles], dtype=bool)
    return handles, P1, P2, y


# ---- deterministic_v1 detector --------------------------------------------
def detect(P1: np.ndarray, P2: np.ndarray) -> np.ndarray:
    n = len(P1)
    if n == 0:
        return np.zeros(0, dtype=bool)
    d = P2 - P1
    L = np.hypot(d[:, 0], d[:, 1])
    ang = np.arctan2(d[:, 1], d[:, 0]) % math.pi
    mid = (P1 + P2) * 0.5
    U = d / L[:, None]  # unit directions
    tree = cKDTree(mid)
    radii = L + GAP_MAX
    nbrs = tree.query_ball_point(mid, radii)  # per-point radius
    has = np.zeros(n, dtype=bool)
    for i in range(n):
        J = nbrs[i]
        if len(J) <= 1:
            continue
        J = np.fromiter((j for j in J if j != i), dtype=np.int64)
        if J.size == 0:
            continue
        da = np.abs(ang[i] - ang[J]); da = np.minimum(da, math.pi - da)
        par = da <= ANGLE_TOL
        if not par.any():
            continue
        Jp = J[par]
        w = mid[Jp] - P1[i]
        perp = np.abs(w[:, 0] * (-U[i, 1]) + w[:, 1] * U[i, 0])
        inband = (perp >= GAP_MIN) & (perp <= GAP_MAX)
        if not inband.any():
            continue
        Jb = Jp[inband]
        tj1 = (P1[Jb] - P1[i]) @ U[i]
        tj2 = (P2[Jb] - P1[i]) @ U[i]
        lo = np.minimum(tj1, tj2); hi = np.maximum(tj1, tj2)
        ov = np.minimum(hi, L[i]) - np.maximum(lo, 0.0)
        ov = np.clip(ov, 0.0, None)
        minlen = np.minimum(L[i], L[Jb])
        ok = ov >= OVERLAP_FRAC * minlen
        if ok.any():
            has[i] = True
            has[Jb[ok]] = True
    return has & (L >= LEN_MIN)


# ---- Transforms ------------------------------------------------------------
def bbox_diag_centroid(P1, P2):
    allp = np.vstack([P1, P2])
    lo = allp.min(0); hi = allp.max(0)
    D = float(np.hypot(*(hi - lo)))
    c = (lo + hi) * 0.5
    return D, c


def t_translate(P1, P2, D, c, prm):
    v = np.array([prm["dx_over_D"] * D, prm["dy_over_D"] * D])
    return P1 + v, P2 + v, None


def t_rotate(P1, P2, D, c, prm):
    th = math.radians(prm["deg"])
    R = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    return (P1 - c) @ R.T + c, (P2 - c) @ R.T + c, None


def t_scale(P1, P2, D, c, prm):
    s = prm["factor"]
    return (P1 - c) * s + c, (P2 - c) * s + c, None


def t_jitter(P1, P2, D, c, prm):
    """Deterministic bounded dither of shared logical vertices (doe_P5 2.2)."""
    q = prm["q_over_D"] * D
    seed = int(prm["seed"])
    eps = 1e-6 * D if D > 0 else 1e-6
    verts = np.vstack([P1, P2])
    keys = np.round(verts / eps).astype(np.int64)
    moved = verts.copy()
    cache = {}
    for idx in range(len(verts)):
        k = (int(keys[idx, 0]), int(keys[idx, 1]))
        off = cache.get(k)
        if off is None:
            hd = hashlib.sha256(f"{seed}|{k[0]}|{k[1]}".encode()).digest()
            ax = (int.from_bytes(hd[0:8], "little") / 2**64) * 2 - 1
            ay = (int.from_bytes(hd[8:16], "little") / 2**64) * 2 - 1
            nrm = math.hypot(ax, ay) or 1.0
            off = np.array([ax / nrm * q, ay / nrm * q])
            cache[k] = off
        moved[idx] = verts[idx] + off
    n = len(P1)
    nP1 = moved[:n]; nP2 = moved[n:]
    # INVALID_TRANSFORM: segments that became zero-length are excluded from denom
    zero = np.hypot(nP2[:, 0] - nP1[:, 0], nP2[:, 1] - nP1[:, 1]) == 0.0
    valid_mask = ~zero
    return nP1, nP2, valid_mask


TRANSFORM_FUNCS = {"translate": t_translate, "rotate": t_rotate,
                   "uniform-scale": t_scale, "coord-jitter": t_jitter}
MEASURABLE = ["F01", "F02", "F03", "F07"]
BLOCKED = ["F04", "F05", "F06"]


def verdict(rmeta: float) -> str:
    if rmeta <= 0.02:
        return "PASS"
    if rmeta <= 0.10:
        return "INCONCLUSIVE"
    return "FAIL"


def main():
    t0 = time.time()
    dev_ids = json.loads(MANIFEST.read_text(encoding="utf-8"))["frozen"]["splits"]["A"]["drawing_ids"]
    assert len(dev_ids) == 198

    # cache base geometry + base prediction + truth per drawing
    base = {}
    tot_wall = 0; tot_pred_wall = 0; tot_seg = 0; tot_tp = 0
    macro_recall = []
    invalid_drawings = []
    for did in dev_ids:
        handles, P1, P2, y = load_drawing(did)
        if len(P1) == 0:
            invalid_drawings.append(did)
            continue
        pred = detect(P1, P2)
        base[did] = (P1, P2, pred)
        tot_seg += len(pred)
        tot_wall += int(y.sum())
        tot_pred_wall += int(pred.sum())
        tp = int((pred & y).sum())
        tot_tp += tp
        if int(y.sum()) > 0:
            macro_recall.append(tp / int(y.sum()))

    # deterministic self-check (Q2 repeat checksum)
    probe = dev_ids[0]
    p1, p2, pr = base[probe]
    assert np.array_equal(pr, detect(p1, p2)), "repeat checksum FAIL (nondeterministic)"

    pooled_recall = (tot_tp / tot_wall) if tot_wall else 0.0
    pred_rate = (tot_pred_wall / tot_seg) if tot_seg else 0.0
    macro_recall_mean = float(np.mean(macro_recall)) if macro_recall else 0.0
    zero_detector_recall = 0.0                     # constant-0 sentinel demonstration
    all_detector_rate = 1.0                        # constant-1 sentinel demonstration
    sentinel_pass = (pooled_recall >= RECALL_FLOOR) and (0.0 < pred_rate < NEAR_ALL)

    # ---- measure R-META for measurable cells ----
    ev_rows = []
    cell_summary = {}
    for fid in MEASURABLE:
        tdef = SPEC["transforms"][fid]
        fn = TRANSFORM_FUNCS[tdef["transform"]]
        drawing_v = []
        for did, (P1, P2, pred0) in base.items():
            D, c = bbox_diag_centroid(P1, P2)
            param_v = []
            for pi, prm in enumerate(tdef["params"]):
                nP1, nP2, vmask = fn(P1, P2, D, c, prm)
                pred1 = detect(nP1, nP2)
                if vmask is None:
                    denom = len(pred0)
                    flips = int(np.count_nonzero(pred0 != pred1))
                else:
                    denom = int(vmask.sum())
                    flips = int(np.count_nonzero((pred0 != pred1) & vmask))
                v = (flips / denom) if denom else 0.0
                param_v.append(v)
                ev_rows.append({"cell_id": fid, "transform": tdef["transform"],
                                "drawing_id": did, "param_idx": pi,
                                "param": json.dumps(prm, separators=(",", ":")),
                                "n_lid": denom, "n_flip": flips,
                                "violation_frac": f"{v:.8f}"})
            drawing_v.append(float(np.mean(param_v)))
        rmeta = float(np.mean(drawing_v))
        vd = verdict(rmeta) if sentinel_pass else "INADMISSIBLE"
        cell_summary[fid] = {"transform": tdef["transform"], "measurability": "MEASURABLE",
                             "r_meta": rmeta, "verdict": vd,
                             "n_drawings": len(drawing_v),
                             "n_params": len(tdef["params"]),
                             "drawing_v_min": float(np.min(drawing_v)),
                             "drawing_v_median": float(np.median(drawing_v)),
                             "drawing_v_max": float(np.max(drawing_v))}
    for fid in BLOCKED:
        tdef = SPEC["transforms"][fid]
        cell_summary[fid] = {"transform": tdef["transform"], "measurability": "BLOCKED_INPUT",
                             "r_meta": None, "verdict": "BLOCKED_INPUT",
                             "reason": tdef["reason"]}

    wall_s = time.time() - t0
    telem = {"wall_seconds": round(wall_s, 3), "peak_rss_bytes": peak_rss_bytes(),
             "peak_vram_bytes": "N/A(no_GPU)", "device": f"CPU {platform.processor() or platform.machine()}",
             "budget_charge_cpu_hours": round(wall_s / 3600.0, 5), "cap_cpu_hours": 4.0}

    # family verdict
    measured_verdicts = [cell_summary[f]["verdict"] for f in MEASURABLE]
    if not sentinel_pass:
        family = "INCOMPLETE(sentinel_ineligible)"
    elif any(v == "FAIL" for v in measured_verdicts):
        family = "FAIL"
    elif any(v == "INCONCLUSIVE" for v in measured_verdicts):
        family = "INCONCLUSIVE(measurable-only; F04-F06 BLOCKED_INPUT)"
    elif all(v == "PASS" for v in measured_verdicts):
        family = "PASS(measurable-only; F04-F06 BLOCKED_INPUT prevents complete family verdict)"
    else:
        family = "INCOMPLETE"

    measurement = {
        "schema": "ariadne.e2.w3.det_v1_relegislate.measurement.v1",
        "method_id": "deterministic_v1", "cell_id": "e2.w3.det_v1_relegislate",
        "spec_sha256": PREREG["spec_sha256"], "code_sha256": CODE_SHA,
        "population": {"name": "val-A DEV", "drawing_count": len(dev_ids),
                       "valid_drawings": len(base), "invalid_drawings": invalid_drawings,
                       "split_content_hash": "5e16541d7191ad01c57a9cee72172f63112ed68590dd371aff5bf0aaaab8e07b"},
        "sentinel_qualification": {
            "positive_recall_floor": RECALL_FLOOR, "pooled_recall": round(pooled_recall, 6),
            "macro_recall_mean": round(macro_recall_mean, 6), "prediction_rate": round(pred_rate, 6),
            "near_all_thresh": NEAR_ALL, "zero_detector_recall": zero_detector_recall,
            "all_detector_rate": all_detector_rate, "sentinel_pass": sentinel_pass,
            "total_walls": tot_wall, "total_true_positive": tot_tp,
            "total_pred_wall": tot_pred_wall, "total_segments": tot_seg},
        "cells": cell_summary, "family_verdict": family, "telemetry": telem,
    }
    (CELL / "measurement.json").write_text(json.dumps(measurement, indent=2, ensure_ascii=False), encoding="utf-8")

    # evidence.csv: per drawing x transform x param, then cell summary rows
    ev_path = CELL / "evidence.csv"
    with ev_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["row_type", "cell_id", "transform", "measurability", "drawing_id",
                    "param_idx", "param", "n_lid", "n_flip", "violation_frac",
                    "r_meta", "verdict"])
        for r in ev_rows:
            w.writerow(["obs", r["cell_id"], r["transform"], "MEASURABLE", r["drawing_id"],
                        r["param_idx"], r["param"], r["n_lid"], r["n_flip"],
                        r["violation_frac"], "", ""])
        for fid in ["F01", "F02", "F03", "F04", "F05", "F06", "F07"]:
            cs = cell_summary[fid]
            w.writerow(["cell_summary", fid, cs["transform"], cs["measurability"], "", "", "",
                        "", "", "", ("" if cs["r_meta"] is None else f"{cs['r_meta']:.8f}"),
                        cs["verdict"]])

    print("CODE_SHA256", CODE_SHA)
    print("sentinel_pass", sentinel_pass, "pooled_recall", round(pooled_recall, 4),
          "pred_rate", round(pred_rate, 4))
    for fid in ["F01", "F02", "F03", "F04", "F05", "F06", "F07"]:
        cs = cell_summary[fid]
        print(fid, cs["transform"], cs["measurability"],
              ("" if cs["r_meta"] is None else f"R-META={cs['r_meta']:.5f}"), cs["verdict"])
    print("family_verdict", family)
    print("wall_seconds", telem["wall_seconds"], "peak_rss_MB", round(telem["peak_rss_bytes"] / 1e6, 1))
    print("AXIS_MEASUREMENT_COMPLETE_V1")


if __name__ == "__main__":
    main()
