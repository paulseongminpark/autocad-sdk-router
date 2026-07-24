#!/usr/bin/env python3
"""S2-F: synthetic-vs-real fidelity comparator (CARD S2-F).

Purpose
-------
Recompute the SAME S2 statistics that S2-A computes from the *real* corpus, but
here FROM a pack of synthetic DXFs (via ezdxf), then measure how far the pack's
distributions sit from the real ones and emit a per-statistic DRAFT verdict.

Statistics (schema tag ``s2.v1``), computed identically for pack and real:
  * parallel-pair offset histogram  -> "wall thickness" distribution
  * entity mix                      -> categorical count per DXF entity type
  * layer tokens                    -> categorical count per layer name

Distances (own stdlib implementations, no scipy):
  * thickness  : two-sample Kolmogorov-Smirnov (KS) statistic
  * categorical: total-variation (TV) distance

Verdicts come from reports/e2/s2/fidelity_bands.json (DRAFT, not yet sealed by
pre-registration). Every verdict carries a ``_DRAFT`` suffix on purpose: this
machinery is complete but the *thresholds* are provisional until prereg seals
them. Do not cite a ``*_DRAFT`` verdict as a passing/failing result.

ezdxf is ALLOWED for this card (per the card contract). Everything else is
Python stdlib. The comparator itself is stdlib-only; ezdxf is used only to read
pack DXFs and (in --selftest) to build a tiny fixture in the OS temp dir.

Run:
  python s2_fidelity.py --selftest
  python s2_fidelity.py compare --pack DIR --real reports/e2/s2/real_stats.json --out R.json
"""
from __future__ import annotations

import argparse
import bisect
import glob
import json
import math
import os
import sys
from pathlib import Path

STATS_SCHEMA = "s2.v1"
REPORT_SCHEMA = "s2.fidelity.v1"

# Repo-root-relative defaults (this file lives at <root>/tools/e2/s2_fidelity.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BANDS = REPO_ROOT / "reports" / "e2" / "s2" / "fidelity_bands.json"
DEFAULT_REAL = REPO_ROOT / "reports" / "e2" / "s2" / "real_stats.json"

# Fixed thickness histogram bin edges (mm). 0..620 in 20mm steps -> 31 bins.
# Fixed so pack and real share identical bins (required for a binned KS fallback).
THICK_EDGES = list(range(0, 621, 20))

# Which stats field each categorical band draws from.
_CATEGORICAL_FIELD = {"entity_mix_tv": "entity_mix", "layer_tokens_tv": "layer_tokens"}


# --------------------------------------------------------------------------- #
# Distance math (stdlib-only, self-contained, unit-tested by --selftest)
# --------------------------------------------------------------------------- #
_FLATTEN_META_KEYS = {"n_defs", "total_entities", "n_pairs", "meta", "stats"}


def _flatten_counts(m):
    """Flatten flat {cat: n} or nested {group: {...: {cat: n}}} count maps to {cat: n}.

    real_stats (rs.v1) nests counts (entity_mix_by_role -> role -> entity_types -> counts;
    layer_tokens -> layer_freq -> counts); pack stats are flat. Meta count keys are skipped
    so document totals don't pollute the categorical distribution.
    """
    flat = {}

    def rec(d):
        for k, v in d.items():
            if k in _FLATTEN_META_KEYS:
                continue
            if isinstance(v, dict):
                rec(v)
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                flat[k] = flat.get(k, 0) + v

    if isinstance(m, dict):
        rec(m)
    return flat


def ks_statistic(a, b):
    """Two-sample Kolmogorov-Smirnov statistic from raw sample lists.

    KS = max_x |F_a(x) - F_b(x)| where F is the empirical CDF. Range [0, 1].
    Raises ValueError on an empty input (undefined CDF).
    """
    if not a or not b:
        raise ValueError("ks_statistic: both sample lists must be non-empty")
    sa = sorted(a)
    sb = sorted(b)
    na = len(sa)
    nb = len(sb)
    d = 0.0
    for x in sorted(set(sa) | set(sb)):
        fa = bisect.bisect_right(sa, x) / na
        fb = bisect.bisect_right(sb, x) / nb
        d = max(d, abs(fa - fb))
    return d


def ks_from_hist(hist_a, hist_b):
    """KS statistic between two histograms that share identical bin edges.

    Compares normalized cumulative counts bin-by-bin, returns the max abs gap.
    Raises ValueError on mismatched edges or an all-zero histogram.
    """
    ea, ca = hist_a["edges"], hist_a["counts"]
    eb, cb = hist_b["edges"], hist_b["counts"]
    if ea != eb:
        raise ValueError("ks_from_hist: histograms must share identical edges")
    ta = sum(ca)
    tb = sum(cb)
    if ta == 0 or tb == 0:
        raise ValueError("ks_from_hist: an empty histogram has no CDF")
    cum_a = 0.0
    cum_b = 0.0
    d = 0.0
    for i in range(len(ca)):
        cum_a += ca[i] / ta
        cum_b += cb[i] / tb
        d = max(d, abs(cum_a - cum_b))
    return d


def total_variation(p_counts, q_counts):
    """Total-variation distance between two categorical count dicts.

    TV(P, Q) = 0.5 * sum_k |P(k) - Q(k)| over the union of categories, with
    P and Q each normalized to sum 1. Range [0, 1].
    Raises ValueError if either side has zero total mass.
    """
    sp = sum(p_counts.values())
    sq = sum(q_counts.values())
    if sp == 0 or sq == 0:
        raise ValueError("total_variation: both distributions must have mass")
    keys = set(p_counts) | set(q_counts)
    return 0.5 * sum(
        abs(p_counts.get(k, 0) / sp - q_counts.get(k, 0) / sq) for k in keys
    )


def _histogram(samples, edges):
    """Bin samples into len(edges)-1 bins; clamp out-of-range into the ends."""
    nb = len(edges) - 1
    counts = [0] * nb
    for v in samples:
        idx = bisect.bisect_right(edges, v) - 1
        if idx < 0:
            idx = 0
        elif idx >= nb:
            idx = nb - 1
        counts[idx] += 1
    return {"edges": list(edges), "counts": counts}


# --------------------------------------------------------------------------- #
# Geometry: parallel-pair offset ("wall thickness") extraction
# --------------------------------------------------------------------------- #
def parallel_pair_offsets(
    segments,
    angle_tol_deg=1.0,
    min_overlap_frac=0.10,
    min_offset=1e-6,
    max_offset=None,
):
    """Perpendicular offsets between overlapping parallel segment pairs.

    A wall drawn as two parallel faces yields one pair whose offset == the wall
    thickness. Each accepted pair contributes one offset sample.

    segments: iterable of ((x1, y1), (x2, y2)).
    """
    sin_tol = math.sin(math.radians(angle_tol_deg))
    # Precompute unit direction, normal and length; drop degenerate segments.
    prepared = []
    for (x1, y1), (x2, y2) in segments:
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length <= 0.0:
            continue
        ux = dx / length
        uy = dy / length
        prepared.append(((x1, y1), (x2, y2), ux, uy, length))

    offsets = []
    n = len(prepared)
    for i in range(n):
        (p0x, p0y), (p1x, p1y), ux, uy, li = prepared[i]
        nx, ny = -uy, ux  # unit normal of segment i
        # segment i projected onto its own direction
        ai0 = p0x * ux + p0y * uy
        ai1 = p1x * ux + p1y * uy
        i_lo, i_hi = (ai0, ai1) if ai0 <= ai1 else (ai1, ai0)
        for j in range(i + 1, n):
            (q0x, q0y), (q1x, q1y), vx, vy, lj = prepared[j]
            # parallel test: |sin(theta)| = |u x v|
            if abs(ux * vy - uy * vx) > sin_tol:
                continue
            # perpendicular offset between the two infinite lines
            offset = abs((q0x - p0x) * nx + (q0y - p0y) * ny)
            if offset <= min_offset:
                continue
            if max_offset is not None and offset > max_offset:
                continue
            # overlap along segment i's direction
            aj0 = q0x * ux + q0y * uy
            aj1 = q1x * ux + q1y * uy
            j_lo, j_hi = (aj0, aj1) if aj0 <= aj1 else (aj1, aj0)
            overlap = min(i_hi, j_hi) - max(i_lo, j_lo)
            if overlap <= min_overlap_frac * min(li, lj):
                continue
            offsets.append(offset)
    return offsets


def _segments_from_msp(msp):
    """Extract 2D line segments from a modelspace (LINE, LWPOLYLINE, POLYLINE)."""
    segs = []
    for e in msp:
        etype = e.dxftype()
        try:
            if etype == "LINE":
                s = e.dxf.start
                t = e.dxf.end
                segs.append(((s.x, s.y), (t.x, t.y)))
            elif etype == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in e.get_points("xy")]
                for k in range(len(pts) - 1):
                    segs.append((pts[k], pts[k + 1]))
                if e.closed and len(pts) >= 2:
                    segs.append((pts[-1], pts[0]))
            elif etype == "POLYLINE":
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
                for k in range(len(pts) - 1):
                    segs.append((pts[k], pts[k + 1]))
                if e.is_closed and len(pts) >= 2:
                    segs.append((pts[-1], pts[0]))
        except Exception:
            # A single malformed entity must not abort the whole pack scan.
            continue
    return segs


# --------------------------------------------------------------------------- #
# Stats computation from a pack of DXFs (ezdxf)
# --------------------------------------------------------------------------- #
def compute_stats_from_pack(pack_dir, thick_edges=THICK_EDGES):
    """Compute the S2 stats dict from every *.dxf under pack_dir (recursive)."""
    import ezdxf  # allowed by card; imported lazily so distance math stays stdlib

    files = sorted(glob.glob(os.path.join(pack_dir, "**", "*.dxf"), recursive=True))
    entity_mix = {}
    layer_tokens = {}
    thickness_samples = []
    errors = []
    n_ok = 0

    for path in files:
        try:
            doc = ezdxf.readfile(path)
        except Exception as exc:  # unreadable / malformed DXF
            errors.append({"file": os.path.relpath(path, pack_dir), "error": str(exc)})
            continue
        n_ok += 1
        msp = doc.modelspace()
        for e in msp:
            etype = e.dxftype()
            entity_mix[etype] = entity_mix.get(etype, 0) + 1
            layer = getattr(e.dxf, "layer", "0")
            layer_tokens[layer] = layer_tokens.get(layer, 0) + 1
        thickness_samples.extend(parallel_pair_offsets(_segments_from_msp(msp)))

    return {
        "stats": STATS_SCHEMA,
        "source": "pack",
        "pack_dir": os.path.abspath(pack_dir),
        "n_drawings": n_ok,
        "n_files_seen": len(files),
        "read_errors": errors,
        "entity_mix": entity_mix,
        "layer_tokens": layer_tokens,
        "thickness_samples": [float(x) for x in thickness_samples],
        "thickness_hist": _histogram(thickness_samples, thick_edges),
    }


# --------------------------------------------------------------------------- #
# WallPlan -> DXF (used only by --selftest to build a fixture in OS temp)
# --------------------------------------------------------------------------- #
def build_wallplan_dxf(plan, path):
    """Render a WallPlan (wp.v1) to an ASCII R2018 DXF.

    Each wall is drawn as its two parallel faces, offset +/- thickness/2 from the
    centerline axis, so parallel_pair_offsets recovers the thickness. This is a
    deliberately minimal renderer for the fidelity fixture, not a full wall CAD.
    """
    import ezdxf

    doc = ezdxf.new("R2018")  # AC1032
    msp = doc.modelspace()
    for w in plan.get("walls", []):
        (x1, y1), (x2, y2) = w["axis"]
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length <= 0.0:
            continue
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        half = float(w["thickness"]) / 2.0
        layer = w.get("layer", "0")
        if layer not in doc.layers:
            doc.layers.add(layer)
        for side in (1.0, -1.0):
            p1 = (x1 + nx * half * side, y1 + ny * half * side)
            p2 = (x2 + nx * half * side, y2 + ny * half * side)
            msp.add_line(p1, p2, dxfattribs={"layer": layer})
    doc.saveas(path)  # ASCII DXF by default
    return path


# --------------------------------------------------------------------------- #
# Bands + comparison
# --------------------------------------------------------------------------- #
def load_bands(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _distance_for(stat_key, spec, pack, real):
    """Return (distance|None, method, (pack_n, real_n)|None) for one statistic."""
    metric = spec.get("metric")
    if metric == "ks":
        pa = pack.get("thickness_samples")
        ra = real.get("thickness_samples")
        if pa and ra:
            return ks_statistic(pa, ra), "ks_raw", (len(pa), len(ra))
        ha = pack.get("thickness_hist")
        hb = real.get("thickness_hist")
        # real_stats (rs.v1, S2-A card) ships a histogram under 'bin_edges' and no raw
        # samples -- rebin the pack's raw samples onto the real edges so both sides share
        # identical bins (ks_from_hist's precondition).
        real_edges = (hb or {}).get("edges") or (hb or {}).get("bin_edges")
        if pa and real_edges and sum((hb or {}).get("counts", [])) > 0:
            counts = [0] * (len(real_edges) - 1)
            for x in pa:
                i = bisect.bisect_right(real_edges, float(x)) - 1
                if 0 <= i < len(counts):
                    counts[i] += 1
            if sum(counts) > 0:
                ha2 = {"edges": real_edges, "counts": counts}
                hb2 = {"edges": real_edges, "counts": hb["counts"]}
                return ks_from_hist(ha2, hb2), "ks_hist_rebinned", (sum(counts), sum(hb["counts"]))
        if (
            ha and hb
            and ha.get("edges") == hb.get("edges")
            and sum(ha.get("counts", [])) > 0
            and sum(hb.get("counts", [])) > 0
        ):
            return (
                ks_from_hist(ha, hb),
                "ks_hist",
                (sum(ha["counts"]), sum(hb["counts"])),
            )
        return None, "no_data", None
    if metric == "tv":
        field = _CATEGORICAL_FIELD.get(stat_key)
        if field is None:
            return None, "no_field_mapping", None
        pm = _flatten_counts(pack.get(field, {}) or {})
        rm = _flatten_counts(real.get(field, {}) or {})
        if sum(pm.values()) > 0 and sum(rm.values()) > 0:
            return total_variation(pm, rm), "tv", (sum(pm.values()), sum(rm.values()))
        return None, "no_data", None
    return None, "unknown_metric", None


def _verdict(distance, method, spec):
    """Map a distance to a DRAFT verdict against a band spec."""
    threshold = spec.get("threshold")
    if threshold is None:
        return "NO_BAND"
    if distance is None:
        return "NO_DATA"
    op = spec.get("op", "<=")
    if op == "<=":
        passed = distance <= threshold
    elif op == "<":
        passed = distance < threshold
    else:
        return "UNKNOWN_OP"
    return spec.get("pass_verdict", "PASS_DRAFT") if passed else spec.get(
        "fail_verdict", "FAIL_DRAFT"
    )


def compare(pack_stats, real_stats, bands):
    """Compute distances + DRAFT verdicts for every band statistic."""
    stat_specs = bands.get("statistics", {})
    stats_out = {}
    for stat_key, spec in stat_specs.items():
        distance, method, ns = _distance_for(stat_key, spec, pack_stats, real_stats)
        verdict = _verdict(distance, method, spec)
        stats_out[stat_key] = {
            "metric": spec.get("metric"),
            "distance": distance,
            "method": method,
            "op": spec.get("op"),
            "threshold": spec.get("threshold"),
            "n_pack": ns[0] if ns else None,
            "n_real": ns[1] if ns else None,
            "verdict": verdict,
        }

    # Overall verdict: only banded statistics (threshold not null) participate.
    banded = [
        s for k, s in stats_out.items()
        if stat_specs.get(k, {}).get("threshold") is not None
    ]
    if not banded:
        overall = "NO_BAND"
    elif any(s["verdict"] == "NO_DATA" for s in banded):
        overall = "INCONCLUSIVE_DRAFT"
    elif any(str(s["verdict"]).startswith("FAIL") for s in banded):
        overall = "FAIL_DRAFT"
    elif all(str(s["verdict"]).startswith("PASS") for s in banded):
        overall = "PASS_DRAFT"
    else:
        overall = "INCONCLUSIVE_DRAFT"

    def _summary(st):
        return {
            "source": st.get("source"),
            "n_drawings": st.get("n_drawings"),
            "entity_types": len(st.get("entity_mix", {})),
            "layer_tokens": len(st.get("layer_tokens", {})),
            "thickness_n": len(st.get("thickness_samples", []) or []),
            "thickness_hist": st.get("thickness_hist"),
            "read_errors": len(st.get("read_errors", []) or []),
        }

    return {
        "report": REPORT_SCHEMA,
        "draft_pending_prereg": bool(bands.get("draft_pending_prereg", True)),
        "bands_tag": bands.get("bands"),
        "pack_summary": _summary(pack_stats),
        "real_summary": _summary(real_stats),
        "statistics": stats_out,
        "overall_verdict": overall,
    }


def _write_json(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")


# --------------------------------------------------------------------------- #
# CLI: compare mode
# --------------------------------------------------------------------------- #
def cmd_compare(args):
    if not os.path.isdir(args.pack):
        print(f"ERROR: --pack is not a directory: {args.pack}", file=sys.stderr)
        return 2
    if not os.path.isfile(args.real):
        print(f"ERROR: --real stats file not found: {args.real}", file=sys.stderr)
        return 2
    if not os.path.isfile(args.bands):
        print(f"ERROR: --bands file not found: {args.bands}", file=sys.stderr)
        return 2

    pack_stats = compute_stats_from_pack(args.pack)
    with open(args.real, "r", encoding="utf-8") as fh:
        real_stats = json.load(fh)
    bands = load_bands(args.bands)

    report = compare(pack_stats, real_stats, bands)
    report["generated_from"] = {
        "pack_dir": os.path.abspath(args.pack),
        "real_stats": os.path.abspath(args.real),
        "bands": os.path.abspath(args.bands),
    }
    _write_json(report, args.out)
    print(f"wrote {args.out}  overall={report['overall_verdict']}")
    for k, s in report["statistics"].items():
        dist = "n/a" if s["distance"] is None else f"{s['distance']:.4f}"
        print(f"  {k}: {s['metric']} distance={dist} verdict={s['verdict']}")
    return 0


# --------------------------------------------------------------------------- #
# CLI: selftest mode
# --------------------------------------------------------------------------- #
def cmd_selftest(_args=None):
    import tempfile

    failures = []

    def check(name, got, want, tol=1e-9):
        ok = abs(got - want) <= tol
        print(f"[{'OK' if ok else 'FAIL'}] {name}: got={got:.6f} want={want:.6f}")
        if not ok:
            failures.append(name)

    def check_true(name, cond, detail=""):
        print(f"[{'OK' if cond else 'FAIL'}] {name}{(' ' + detail) if detail else ''}")
        if not cond:
            failures.append(name)

    print("== Part A: distance math on synthesized stat dicts ==")
    # -- KS from raw samples --
    check("ks_identical", ks_statistic([1, 2, 3, 4], [1, 2, 3, 4]), 0.0)
    check("ks_disjoint", ks_statistic([1, 2, 3, 4], [5, 6, 7, 8]), 1.0)
    check("ks_shift", ks_statistic([1, 2, 3, 4], [3, 4, 5, 6]), 0.5)
    # -- KS from histograms (shared edges) --
    ha = {"edges": [0, 1, 2, 3], "counts": [4, 0, 0]}
    hb = {"edges": [0, 1, 2, 3], "counts": [0, 0, 4]}
    check("ks_hist_disjoint", ks_from_hist(ha, hb), 1.0)
    hc = {"edges": [0, 1, 2, 3], "counts": [2, 2, 0]}
    hd = {"edges": [0, 1, 2, 3], "counts": [0, 2, 2]}
    check("ks_hist_shift", ks_from_hist(hc, hd), 0.5)
    # -- Total variation on categorical mixes --
    check("tv_identical", total_variation({"A": 1, "B": 1}, {"A": 1, "B": 1}), 0.0)
    check("tv_disjoint", total_variation({"A": 1}, {"B": 1}), 1.0)
    check(
        "tv_partial",
        total_variation({"LINE": 8, "ARC": 2}, {"LINE": 6, "ARC": 4}),
        0.2,
    )
    # -- error paths raise, not silently pass --
    try:
        ks_statistic([], [1])
        check_true("ks_empty_raises", False)
    except ValueError:
        check_true("ks_empty_raises", True)
    try:
        total_variation({}, {"A": 1})
        check_true("tv_empty_raises", False)
    except ValueError:
        check_true("tv_empty_raises", True)

    print("== Part B: ezdxf recompute path (fixture built in OS temp) ==")
    tmpdir = tempfile.mkdtemp(prefix="s2f_selftest_")
    pack_dir = os.path.join(tmpdir, "pack")
    os.makedirs(pack_dir, exist_ok=True)
    plan = {
        "plan": "wp.v1",
        "seed": 7,
        "units": "mm",
        "walls": [
            {"id": "w1", "axis": [[0, 0], [5000, 0]], "thickness": 240.0, "layer": "WALL"},
            {"id": "w2", "axis": [[0, 0], [0, 3000]], "thickness": 200.0, "layer": "WALL"},
        ],
        "openings": [],
    }
    dxf_path = build_wallplan_dxf(plan, os.path.join(pack_dir, "d1.dxf"))
    print(f"  built fixture: {dxf_path}")
    stats = compute_stats_from_pack(pack_dir)
    check_true("pack_n_drawings", stats["n_drawings"] == 1, f"n={stats['n_drawings']}")
    check_true(
        "pack_line_count",
        stats["entity_mix"].get("LINE", 0) == 4,
        f"LINE={stats['entity_mix'].get('LINE', 0)}",
    )
    check_true(
        "pack_layer_wall",
        stats["layer_tokens"].get("WALL", 0) == 4,
        f"WALL={stats['layer_tokens'].get('WALL', 0)}",
    )
    ts = sorted(stats["thickness_samples"])
    check_true(
        "pack_thickness_recovered",
        len(ts) == 2 and abs(ts[0] - 200.0) < 1e-6 and abs(ts[1] - 240.0) < 1e-6,
        f"samples={ts}",
    )

    print("== Part C: compare() machinery end-to-end (synthetic 'real') ==")
    real_like = {
        "stats": STATS_SCHEMA,
        "source": "real",
        "n_drawings": 1,
        "thickness_samples": [238.0, 205.0, 241.0, 198.0],
        "entity_mix": {"LINE": 8},
        "layer_tokens": {"WALL": 8},
        "thickness_hist": _histogram([238.0, 205.0, 241.0, 198.0], THICK_EDGES),
    }
    bands = load_bands(DEFAULT_BANDS)
    check_true("bands_draft_flag", bands.get("draft_pending_prereg") is True)
    report = compare(stats, real_like, bands)
    tks = report["statistics"]["thickness_ks"]
    emx = report["statistics"]["entity_mix_tv"]
    lyr = report["statistics"]["layer_tokens_tv"]
    check_true(
        "cmp_thickness_ks_ran",
        tks["method"] == "ks_raw"
        and tks["distance"] is not None
        and 0.0 <= tks["distance"] <= 1.0
        and str(tks["verdict"]).endswith("_DRAFT"),
        f"ks={tks['distance']} verdict={tks['verdict']}",
    )
    check_true(
        "cmp_entity_tv_pass",
        emx["distance"] is not None
        and abs(emx["distance"]) < 1e-9
        and emx["verdict"] == "PASS_DRAFT",
        f"tv={emx['distance']} verdict={emx['verdict']}",
    )
    check_true(
        "cmp_layer_no_band",
        lyr["verdict"] == "NO_BAND",
        f"verdict={lyr['verdict']}",
    )
    # Exercise the JSON write/read path used by compare mode.
    out_path = os.path.join(tmpdir, "R.json")
    _write_json(report, out_path)
    with open(out_path, "r", encoding="utf-8") as fh:
        roundtrip = json.load(fh)
    check_true(
        "report_json_roundtrip",
        roundtrip.get("report") == REPORT_SCHEMA
        and "statistics" in roundtrip
        and roundtrip.get("overall_verdict", "").endswith("_DRAFT"),
        f"overall={roundtrip.get('overall_verdict')}",
    )
    print(f"  wrote+reread report: {out_path}")

    print("== SELFTEST SUMMARY ==")
    total = 17  # keep in sync with the checks above
    if failures:
        print(f"RESULT: FAIL ({len(failures)} failing): {', '.join(failures)}")
        return 1
    print("RESULT: PASS (all distance-math + ezdxf-recompute + compare checks passed)")
    return 0


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def build_parser():
    p = argparse.ArgumentParser(
        prog="s2_fidelity.py",
        description="S2-F synthetic-vs-real fidelity comparator (CARD S2-F).",
    )
    p.add_argument(
        "--selftest",
        action="store_true",
        help="Run the self-contained selftest (builds its own fixture in OS temp).",
    )
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("compare", help="Compare a pack of DXFs against real stats.")
    c.add_argument("--pack", required=True, help="Directory of synthetic pack DXFs.")
    c.add_argument("--real", default=str(DEFAULT_REAL), help="S2-A real stats JSON.")
    c.add_argument("--out", required=True, help="Output report JSON path (R.json).")
    c.add_argument("--bands", default=str(DEFAULT_BANDS), help="Fidelity bands JSON.")

    sub.add_parser("selftest", help="Alias for --selftest.")
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    if args.selftest or args.cmd == "selftest":
        return cmd_selftest(args)
    if args.cmd == "compare":
        return cmd_compare(args)
    build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
