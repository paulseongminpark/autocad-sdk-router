#!/usr/bin/env python
"""S1-C: bbox derivability + unit anchoring audit over E1 projection shards.

Forensic, deterministic. Parses the E1 projection grammar out of the `prompt`
field of bench/e1_shards/shard_NN.jsonl, then measures:

  1. bbox derivability per def (needs >= 1 LINE; projections carry coords only
     on LINE entities -- LWPOLYLINE/ARC/CIRCLE etc. are coordinate-free).
  2. bbox span magnitude class (<10, 10-1e2, 1e2-1e4, 1e4-1e6, >=1e6).
  3. coordinate magnitude distribution (LINE endpoint |x|,|y|).
  4. numeric text tokens (candidate dimension values) vs LINE span ratios,
     i.e. how often a drawn distance is anchored by a printed dimension.

Produces the measurement table S4-C consumes. It states hypotheses with their
supporting counts; it does not issue a unit verdict.

Usage:
    python s1_bbox_units.py                 # RUN over bench/e1_shards/*.jsonl
    python s1_bbox_units.py --selftest      # self-contained fixture check
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
import tempfile

SCHEMA = "e2.s1.bbox_units/v1"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SHARD_GLOB = os.path.join(REPO, "bench", "e1_shards", "shard_*.jsonl")
OUT_JSON = os.path.join(REPO, "reports", "e2", "s1", "bbox_units.json")
OUT_MD = os.path.join(REPO, "reports", "e2", "s1", "bbox_units.md")

# --- projection grammar ------------------------------------------------------

RE_DEFNAME = re.compile(r"^Definition name:\s*(.*)$")
RE_ENTCOUNT = re.compile(r"^entity_count:\s*(\d+)\s*$")
RE_DXFHIST = re.compile(r"^dxf_name histogram:\s*(.*)$")
RE_LAYERHIST = re.compile(r"^layer histogram:\s*(.*)$")
RE_BBOX = re.compile(r"^bbox from LINE start/end:\s*(.*)$")
RE_BBOX_LIST = re.compile(r"^\[\s*([^\]]*)\]\s*$")

RE_ENT = re.compile(r"^-\s+(\S+)\s*(.*)$")
RE_LAYER = re.compile(r"\blayer=(\S+)")
RE_HANDLE = re.compile(r"\bhandle=(\S+)")
RE_COORDS = re.compile(
    r"\(\s*(-?[\d.]+(?:[eE][+-]?\d+)?)\s*,\s*(-?[\d.]+(?:[eE][+-]?\d+)?)\s*\)"
    r"\s*->\s*"
    r"\(\s*(-?[\d.]+(?:[eE][+-]?\d+)?)\s*,\s*(-?[\d.]+(?:[eE][+-]?\d+)?)\s*\)"
)
RE_QUOTED = re.compile(r"'(.*)'\s*$")
RE_RADIUS = re.compile(r"\bradius=(-?[\d.]+(?:[eE][+-]?\d+)?)")
RE_VERTS = re.compile(r"\bvertices=(\d+)")

# MTEXT inline formatting codes: \A1;  \W0.8;  \H2x;  \fArial|b0;  ...
RE_MTEXT_CODE = re.compile(r"\\[A-Za-z][^;\\]*;")
RE_PURE_NUM = re.compile(r"^\d+(?:\.\d+)?$")
RE_EMBEDDED_NUM = re.compile(r"\d+(?:\.\d+)?")

# entity kinds that the E1 projection is known to emit
KNOWN_KINDS = {
    "LINE", "INSERT", "MTEXT", "TEXT", "POINT", "LWPOLYLINE", "WIPEOUT",
    "SPLINE", "HATCH", "ARC", "CIRCLE", "ELLIPSE", "3DFACE",
}

# --- magnitude classes -------------------------------------------------------

MAG_CLASSES = [
    ("lt_10", 0.0, 10.0, "<10"),
    ("10_1e2", 10.0, 1e2, "10-1e2"),
    ("1e2_1e4", 1e2, 1e4, "1e2-1e4"),
    ("1e4_1e6", 1e4, 1e6, "1e4-1e6"),
    ("ge_1e6", 1e6, float("inf"), ">=1e6"),
]

# Ratio buckets for numeric-token / drawn-span. A ratio of ~1 means the drawing
# unit and the printed dimension unit coincide (scale factor 1.0). The rest are
# the classic unit-mismatch factors, kept so a non-1.0 anchor is not silently
# lumped into "other".
RATIO_BUCKETS = [
    ("r_1", 1.0, "1:1 (drawing unit == dim display unit)"),
    ("r_10", 10.0, "10x (cm<->mm class)"),
    ("r_25_4", 25.4, "25.4x (inch->mm)"),
    ("r_304_8", 304.8, "304.8x (foot->mm)"),
    ("r_1000", 1000.0, "1000x (m->mm)"),
]
TOL = 0.01  # 1% relative tolerance, per card


def mag_class(v):
    """Magnitude class key for a non-negative magnitude, or None if not finite."""
    if v is None:
        return None
    try:
        v = abs(float(v))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    for key, lo, hi, _label in MAG_CLASSES:
        if lo <= v < hi:
            return key
    return MAG_CLASSES[-1][0]


def _empty_mag_counter():
    return {key: 0 for key, _lo, _hi, _lab in MAG_CLASSES}


def strip_mtext_codes(s):
    """Remove MTEXT inline formatting codes and brace groups."""
    prev = None
    out = s
    while prev != out:
        prev = out
        out = RE_MTEXT_CODE.sub("", out)
    out = out.replace("{", "").replace("}", "")
    out = out.replace("\\P", " ").replace("\\~", " ")
    return out.strip()


# --- parsing -----------------------------------------------------------------

def parse_entity(line):
    """Parse one '- KIND ...' projection line.

    Unknown / malformed shapes degrade to kind='other'; never raises.
    """
    ent = {
        "kind": "other", "layer": None, "handle": None, "raw": line,
        "coords": None, "text": None, "radius": None, "vertices": None,
    }
    m = RE_ENT.match(line.strip())
    if not m:
        return ent
    kind, rest = m.group(1), m.group(2)
    ent["kind"] = kind if kind in KNOWN_KINDS else "other"
    if ent["kind"] == "other":
        ent["unknown_token"] = kind

    ml = RE_LAYER.search(rest)
    if ml:
        ent["layer"] = ml.group(1)
    mh = RE_HANDLE.search(rest)
    if mh:
        ent["handle"] = mh.group(1)

    mc = RE_COORDS.search(rest)
    if mc:
        try:
            ent["coords"] = tuple(float(g) for g in mc.groups())
        except ValueError:
            ent["coords"] = None

    mq = RE_QUOTED.search(rest)
    if mq:
        ent["text"] = mq.group(1)

    mr = RE_RADIUS.search(rest)
    if mr:
        try:
            ent["radius"] = float(mr.group(1))
        except ValueError:
            pass
    mv = RE_VERTS.search(rest)
    if mv:
        ent["vertices"] = int(mv.group(1))
    return ent


def parse_histogram(s):
    """'A=1, B=2' -> {'A': 1, 'B': 2}; tolerant of junk."""
    out = {}
    for part in s.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.rpartition("=")
        try:
            out[k.strip()] = int(v.strip())
        except ValueError:
            continue
    return out


def parse_projection(prompt):
    """Parse a projection block. Returns a dict; records parse issues inline."""
    rec = {
        "def_name": None, "entity_count": None,
        "dxf_hist": {}, "layer_hist": {},
        "bbox_declared": None, "bbox_declared_raw": None,
        "entities": [], "parse_issues": [],
    }
    for raw in prompt.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("- "):
            rec["entities"].append(parse_entity(line))
            continue
        m = RE_DEFNAME.match(line)
        if m:
            rec["def_name"] = m.group(1).strip()
            continue
        m = RE_ENTCOUNT.match(line)
        if m:
            rec["entity_count"] = int(m.group(1))
            continue
        m = RE_DXFHIST.match(line)
        if m:
            rec["dxf_hist"] = parse_histogram(m.group(1))
            continue
        m = RE_LAYERHIST.match(line)
        if m:
            rec["layer_hist"] = parse_histogram(m.group(1))
            continue
        m = RE_BBOX.match(line)
        if m:
            val = m.group(1).strip()
            rec["bbox_declared_raw"] = val
            lm = RE_BBOX_LIST.match(val)
            if lm:
                try:
                    nums = [float(x.strip()) for x in lm.group(1).split(",") if x.strip()]
                    rec["bbox_declared"] = nums if len(nums) == 6 else None
                    if len(nums) != 6:
                        rec["parse_issues"].append("bbox_declared_arity=%d" % len(nums))
                except ValueError:
                    rec["parse_issues"].append("bbox_declared_unparsed")
            continue
    return rec


# --- measurement -------------------------------------------------------------

def numeric_tokens(entities):
    """Candidate dimension values from MTEXT/TEXT, tagged by provenance.

    MTEXT '\\A1;3280'  -> pure numeric after code-strip  -> dimension candidate.
    TEXT  '84A' / '(84A+84B)45F' -> label; digits embedded in an apartment-type
    code are NOT dimensions, so they are recorded but excluded from anchoring.
    """
    toks = []
    for e in entities:
        if e["kind"] not in ("MTEXT", "TEXT") or e["text"] is None:
            continue
        body = strip_mtext_codes(e["text"]) if e["kind"] == "MTEXT" else e["text"].strip()
        if RE_PURE_NUM.match(body):
            toks.append({
                "handle": e["handle"], "src": e["kind"], "raw": e["text"],
                "value": float(body), "provenance": "pure_numeric",
                "dimension_candidate": True,
            })
        else:
            for hit in RE_EMBEDDED_NUM.findall(body):
                toks.append({
                    "handle": e["handle"], "src": e["kind"], "raw": e["text"],
                    "value": float(hit), "provenance": "label_embedded",
                    "dimension_candidate": False,
                })
    return toks


def bbox_from_lines(entities):
    """Recompute bbox from LINE endpoints only (mirrors the projection's rule)."""
    pts = []
    for e in entities:
        if e["kind"] == "LINE" and e["coords"]:
            x0, y0, x1, y1 = e["coords"]
            pts.append((x0, y0))
            pts.append((x1, y1))
    if not pts:
        return None, pts
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), 0.0, max(xs), max(ys), 0.0), pts


def line_spans(entities):
    spans = []
    for e in entities:
        if e["kind"] == "LINE" and e["coords"]:
            x0, y0, x1, y1 = e["coords"]
            spans.append({
                "handle": e["handle"],
                "len": math.hypot(x1 - x0, y1 - y0),
                "dx": abs(x1 - x0),
                "dy": abs(y1 - y0),
            })
    return spans


def _best_ratio(value, candidates):
    """Candidate whose ratio to `value` is closest to 1.0 in log space."""
    best = None
    for c in candidates:
        if c is None or c <= 0 or value <= 0:
            continue
        ratio = value / c
        d = abs(math.log(ratio))
        if best is None or d < best[0]:
            best = (d, ratio, c)
    if best is None:
        return None, None
    return best[1], best[2]


def _within(a, b, tol=TOL):
    if a is None or b is None:
        return False
    return abs(a - b) <= tol * max(abs(a), 1e-9)


def measure_def(rec, unit_id):
    """All per-def measurements. Pure function of the parsed projection."""
    ents = rec["entities"]
    n_line = sum(1 for e in ents if e["kind"] == "LINE")
    bbox_calc, pts = bbox_from_lines(ents)
    spans = line_spans(ents)
    toks = numeric_tokens(ents)

    out = {
        "unit_id": unit_id,
        "def_name": rec["def_name"],
        "entity_count": rec["entity_count"],
        "n_sampled": len(ents),
        "sample_truncated": bool(
            rec["entity_count"] is not None and rec["entity_count"] > len(ents)
        ),
        "n_line_sampled": n_line,
        "n_line_declared": rec["dxf_hist"].get("LINE", 0),
        # Authoritative: the dxf histogram counts LINEs over the FULL def, so it
        # answers "derivable?" even when the 30-entity sample shows no LINE.
        "bbox_derivable": rec["dxf_hist"].get("LINE", 0) > 0,
        "bbox_derivable_from_sample": bbox_calc is not None,
        "bbox_declared_present": rec["bbox_declared"] is not None,
        "bbox_declared_raw": rec["bbox_declared_raw"],
        "bbox_calc": list(bbox_calc) if bbox_calc else None,
        "parse_issues": list(rec["parse_issues"]),
        "kind_hist": {},
        "other_kind_tokens": sorted(
            {e.get("unknown_token") for e in ents
             if e["kind"] == "other" and e.get("unknown_token")}
        ),
    }
    for e in ents:
        out["kind_hist"][e["kind"]] = out["kind_hist"].get(e["kind"], 0) + 1

    dec = rec["bbox_declared"]

    # --- authoritative basis ---------------------------------------------
    # The declared header bbox is built by the E1 projection from the FULL entity
    # set; the entity list is capped at 30. So for a truncated def the recomputed
    # bbox is sample-limited and understates the true extent. Declared wins when
    # present; recomputed is retained as a cross-check only.
    if dec:
        out["bbox_basis"] = "declared_header"
        span_x, span_y = dec[3] - dec[0], dec[4] - dec[1]
        out["bbox_declared_z"] = [dec[2], dec[5]]
        out["nonplanar_z"] = (dec[2] != 0.0 or dec[5] != 0.0)
    elif bbox_calc:
        out["bbox_basis"] = "recomputed_from_sample"
        span_x, span_y = bbox_calc[3] - bbox_calc[0], bbox_calc[4] - bbox_calc[1]
        out["bbox_declared_z"] = None
        out["nonplanar_z"] = None
    else:
        out["bbox_basis"] = None
        span_x = span_y = None
        out["bbox_declared_z"] = None
        out["nonplanar_z"] = None

    if span_x is not None:
        out["bbox_span_x"] = span_x
        out["bbox_span_y"] = span_y
        out["bbox_span_max"] = max(span_x, span_y)
        out["bbox_span_class"] = mag_class(out["bbox_span_max"])
        out["degenerate_span"] = (out["bbox_span_max"] == 0.0)
    else:
        out["bbox_span_x"] = out["bbox_span_y"] = out["bbox_span_max"] = None
        out["bbox_span_class"] = None
        out["degenerate_span"] = None

    # sample-limited recomputation, kept for the cross-check below
    if bbox_calc:
        out["bbox_span_x_calc"] = bbox_calc[3] - bbox_calc[0]
        out["bbox_span_y_calc"] = bbox_calc[4] - bbox_calc[1]
        out["bbox_span_max_calc"] = max(out["bbox_span_x_calc"], out["bbox_span_y_calc"])
    else:
        out["bbox_span_x_calc"] = out["bbox_span_y_calc"] = out["bbox_span_max_calc"] = None

    # --- declared vs recomputed cross-check (XY only) ---------------------
    # Z is excluded on purpose: the projection renders LINE coords as 2D (x,y)
    # and drops Z, while the declared bbox retains real Z extents. Comparing Z
    # would flag every non-planar def as a phantom mismatch.
    if dec and bbox_calc:
        xy_dec = (dec[0], dec[1], dec[3], dec[4])
        xy_cal = (bbox_calc[0], bbox_calc[1], bbox_calc[3], bbox_calc[4])
        deltas = [abs(a - b) for a, b in zip(xy_dec, xy_cal)]
        out["bbox_declared_max_delta"] = max(deltas)
        out["bbox_declared_matches_calc"] = max(deltas) <= 1e-6
        # a sample-limited bbox must sit INSIDE the full-set bbox
        contained = (
            bbox_calc[0] >= dec[0] - 1e-6 and bbox_calc[1] >= dec[1] - 1e-6
            and bbox_calc[3] <= dec[3] + 1e-6 and bbox_calc[4] <= dec[4] + 1e-6
        )
        out["bbox_calc_within_declared"] = contained
        if out["bbox_declared_matches_calc"]:
            out["bbox_mismatch_reason"] = None
        elif out["sample_truncated"] and contained:
            out["bbox_mismatch_reason"] = "sample_truncated"
        elif contained:
            out["bbox_mismatch_reason"] = "declared_wider_untruncated"
        else:
            out["bbox_mismatch_reason"] = "UNEXPLAINED_calc_escapes_declared"
    else:
        out["bbox_declared_matches_calc"] = None
        out["bbox_declared_max_delta"] = None
        out["bbox_calc_within_declared"] = None
        out["bbox_mismatch_reason"] = None

    # --- coordinate magnitudes -------------------------------------------
    # Extremes come from the declared bbox corners (full-set) when available;
    # sampled LINE endpoints only cover <=30 entities.
    if dec:
        coord_mags = [abs(dec[0]), abs(dec[1]), abs(dec[3]), abs(dec[4])]
        out["coord_basis"] = "declared_bbox_corners"
    else:
        coord_mags = [abs(v) for (x, y) in pts for v in (x, y)]
        out["coord_basis"] = "sampled_line_endpoints" if coord_mags else None
    out["n_coord_samples"] = len(coord_mags)
    out["coord_abs_max"] = max(coord_mags) if coord_mags else None
    out["coord_abs_min"] = min(coord_mags) if coord_mags else None
    out["coord_class_max"] = mag_class(out["coord_abs_max"])

    # span magnitudes
    out["n_line_spans"] = len(spans)
    out["line_span_max"] = max((s["len"] for s in spans), default=None)
    out["line_span_min"] = min((s["len"] for s in spans), default=None)

    # numeric tokens
    dim_toks = [t for t in toks if t["dimension_candidate"]]
    out["n_numeric_tokens_total"] = len(toks)
    out["n_dim_candidates"] = len(dim_toks)
    out["n_label_embedded"] = len(toks) - len(dim_toks)
    out["dim_candidate_values"] = [t["value"] for t in dim_toks]
    out["dim_candidate_class_max"] = mag_class(
        max(out["dim_candidate_values"]) if out["dim_candidate_values"] else None
    )

    # --- unit anchoring ---
    span_lens = [s["len"] for s in spans]
    span_axis = [s["dx"] for s in spans] + [s["dy"] for s in spans]
    bbox_dims = []
    if out["bbox_span_x"] is not None:
        bbox_dims = [out["bbox_span_x"], out["bbox_span_y"]]

    anchor = {
        "line_span_1pct": False,      # card's primary metric
        "line_axis_1pct": False,      # axis-projected LINE extent
        "bbox_span_1pct": False,      # extension-line separation
        "any_1pct": False,
        "best_ratio_vs_line_span": None,
        "best_ratio_vs_bbox_span": None,
        "matches": [],
    }
    for t in dim_toks:
        v = t["value"]
        hit_line = any(_within(v, s) for s in span_lens)
        hit_axis = any(_within(v, s) for s in span_axis)
        hit_bbox = any(_within(v, b) for b in bbox_dims)
        anchor["line_span_1pct"] |= hit_line
        anchor["line_axis_1pct"] |= hit_axis
        anchor["bbox_span_1pct"] |= hit_bbox
        r_line, m_line = _best_ratio(v, span_lens)
        r_bbox, m_bbox = _best_ratio(v, bbox_dims)
        if r_line is not None and (
            anchor["best_ratio_vs_line_span"] is None
            or abs(math.log(r_line)) < abs(math.log(anchor["best_ratio_vs_line_span"]))
        ):
            anchor["best_ratio_vs_line_span"] = r_line
        if r_bbox is not None and (
            anchor["best_ratio_vs_bbox_span"] is None
            or abs(math.log(r_bbox)) < abs(math.log(anchor["best_ratio_vs_bbox_span"]))
        ):
            anchor["best_ratio_vs_bbox_span"] = r_bbox
        anchor["matches"].append({
            "handle": t["handle"], "value": v,
            "hit_line_span": hit_line, "hit_line_axis": hit_axis,
            "hit_bbox_span": hit_bbox,
            "ratio_vs_nearest_line_span": r_line,
            "nearest_line_span": m_line,
            "ratio_vs_nearest_bbox_span": r_bbox,
            "nearest_bbox_span": m_bbox,
        })
    anchor["any_1pct"] = (
        anchor["line_span_1pct"] or anchor["line_axis_1pct"] or anchor["bbox_span_1pct"]
    )
    out["anchor"] = anchor
    out["anchorable"] = bool(dim_toks) and bool(spans)
    return out


def ratio_bucket(r):
    if r is None:
        return None
    for key, target, _label in RATIO_BUCKETS:
        if _within(r, target):
            return key
    return "other"


# --- aggregation -------------------------------------------------------------

def _pct(n, d):
    return round(100.0 * n / d, 2) if d else None


def _median(xs):
    s = sorted(xs)
    if not s:
        return None
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def aggregate(per_def, inputs_meta):
    n = len(per_def)
    derivable = [d for d in per_def if d["bbox_derivable"]]
    nonderiv = [d for d in per_def if not d["bbox_derivable"]]

    # --- bbox derivability ---
    deriv_block = {
        "n_defs": n,
        "bbox_derivable": len(derivable),
        "bbox_not_derivable": len(nonderiv),
        "bbox_derivable_pct": _pct(len(derivable), n),
        "declared_present_and_derivable": sum(
            1 for d in per_def if d["bbox_declared_present"] and d["bbox_derivable"]
        ),
        "declared_absent_and_not_derivable": sum(
            1 for d in per_def if not d["bbox_declared_present"] and not d["bbox_derivable"]
        ),
        "declared_vs_calc_mismatch": sum(
            1 for d in per_def if d["bbox_declared_matches_calc"] is False
        ),
        "declared_vs_calc_checked": sum(
            1 for d in per_def if d["bbox_declared_matches_calc"] is not None
        ),
        "mismatch_reasons": {},
        "calc_escapes_declared": sum(
            1 for d in per_def
            if d.get("bbox_mismatch_reason") == "UNEXPLAINED_calc_escapes_declared"
        ),
        "derivable_vs_declared_disagree": sum(
            1 for d in per_def if d["bbox_derivable"] != d["bbox_declared_present"]
        ),
        "nonplanar_z_defs": sum(1 for d in per_def if d.get("nonplanar_z")),
        "degenerate_span_zero": sum(1 for d in derivable if d["degenerate_span"]),
        "sample_truncated_defs": sum(1 for d in per_def if d["sample_truncated"]),
        "truncated_and_derivable": sum(
            1 for d in per_def if d["sample_truncated"] and d["bbox_derivable"]
        ),
        "line_declared_but_none_sampled": sum(
            1 for d in per_def if d["n_line_declared"] > 0 and d["n_line_sampled"] == 0
        ),
        "basis_note": (
            "bbox_derivable uses the dxf_name histogram (full def). Spans use the "
            "declared header bbox (built from all entities); the recomputed bbox is "
            "sample-limited to <=30 entities and is used only as a cross-check."
        ),
    }
    for d in per_def:
        r = d.get("bbox_mismatch_reason")
        if r:
            deriv_block["mismatch_reasons"][r] = deriv_block["mismatch_reasons"].get(r, 0) + 1

    # why not derivable: what do the LINE-less defs contain?
    kinds_in_nonderiv = {}
    for d in nonderiv:
        for k, c in d["kind_hist"].items():
            kinds_in_nonderiv[k] = kinds_in_nonderiv.get(k, 0) + c
    deriv_block["nonderivable_kind_totals"] = dict(
        sorted(kinds_in_nonderiv.items(), key=lambda kv: -kv[1])
    )

    # --- span magnitude classes ---
    span_classes = {}
    for key, _lo, _hi, label in MAG_CLASSES:
        members = [d for d in derivable if d["bbox_span_class"] == key]
        span_classes[key] = {
            "label": label,
            "n_defs": len(members),
            "pct_of_derivable": _pct(len(members), len(derivable)),
            "median_span_max": _median([d["bbox_span_max"] for d in members]),
            "min_span_max": min((d["bbox_span_max"] for d in members), default=None),
            "max_span_max": max((d["bbox_span_max"] for d in members), default=None),
            "unit_ids": [d["unit_id"] for d in members],
        }

    # --- coordinate magnitude distribution ---
    coord_dist = _empty_mag_counter()
    for d in derivable:
        c = d["coord_class_max"]
        if c:
            coord_dist[c] += 1
    coord_maxes = [d["coord_abs_max"] for d in derivable if d["coord_abs_max"] is not None]
    coord_block = {
        "basis": "per-def max |x|,|y| over LINE endpoints",
        "n_defs_with_coords": len(coord_maxes),
        "class_counts": coord_dist,
        "class_labels": {k: lab for k, _lo, _hi, lab in MAG_CLASSES},
        "median_abs_max": _median(coord_maxes),
        "min_abs_max": min(coord_maxes, default=None),
        "max_abs_max": max(coord_maxes, default=None),
    }

    # --- anchoring ---
    anchorable = [d for d in per_def if d["anchorable"]]
    a_line = [d for d in anchorable if d["anchor"]["line_span_1pct"]]
    a_axis = [d for d in anchorable if d["anchor"]["line_axis_1pct"]]
    a_bbox = [d for d in anchorable if d["anchor"]["bbox_span_1pct"]]
    a_any = [d for d in anchorable if d["anchor"]["any_1pct"]]

    r_line_buckets = {}
    r_bbox_buckets = {}
    for d in anchorable:
        b = ratio_bucket(d["anchor"]["best_ratio_vs_line_span"])
        if b:
            r_line_buckets[b] = r_line_buckets.get(b, 0) + 1
        b = ratio_bucket(d["anchor"]["best_ratio_vs_bbox_span"])
        if b:
            r_bbox_buckets[b] = r_bbox_buckets.get(b, 0) + 1

    anchor_block = {
        "tolerance_pct": TOL * 100,
        "n_defs_with_dim_candidates": sum(1 for d in per_def if d["n_dim_candidates"] > 0),
        "n_defs_anchorable": len(anchorable),
        "anchorable_note": "def has >=1 pure-numeric MTEXT/TEXT token AND >=1 LINE",
        "card_primary_metric": {
            "definition": "defs where some numeric text == a LINE span within 1%",
            "n_hit": len(a_line),
            "n_eligible": len(anchorable),
            "pct": _pct(len(a_line), len(anchorable)),
        },
        "line_axis_1pct": {
            "definition": "numeric text == a LINE's axis-projected dx or dy within 1%",
            "n_hit": len(a_axis), "pct": _pct(len(a_axis), len(anchorable)),
        },
        "bbox_span_1pct": {
            "definition": "numeric text == bbox X or Y span within 1% "
                          "(extension-line separation)",
            "n_hit": len(a_bbox), "pct": _pct(len(a_bbox), len(anchorable)),
        },
        "any_1pct": {"n_hit": len(a_any), "pct": _pct(len(a_any), len(anchorable))},
        "best_ratio_buckets_vs_line_span": r_line_buckets,
        "best_ratio_buckets_vs_bbox_span": r_bbox_buckets,
        "ratio_bucket_labels": {k: lab for k, _t, lab in RATIO_BUCKETS},
        "label_embedded_tokens_excluded": sum(d["n_label_embedded"] for d in per_def),
        "label_exclusion_note": (
            "TEXT like '84A' / '(84A+84B+84C)45F' are apartment-type codes; their "
            "embedded digits are counted but excluded from anchoring as non-dimensions"
        ),
    }

    # --- unit hypothesis table, per span magnitude class ---
    hyp_rows = []
    for key, _lo, _hi, label in MAG_CLASSES:
        members = [d for d in derivable if d["bbox_span_class"] == key]
        if not members:
            hyp_rows.append({
                "span_class": key, "label": label, "n_defs": 0,
                "hypothesis": "no_data", "evidence": "no def in this class",
            })
            continue
        m_anchor = [d for d in members if d["anchorable"]]
        m_hit_any = [d for d in m_anchor if d["anchor"]["any_1pct"]]
        m_hit_1to1 = [
            d for d in m_anchor
            if ratio_bucket(d["anchor"]["best_ratio_vs_bbox_span"]) == "r_1"
            or ratio_bucket(d["anchor"]["best_ratio_vs_line_span"]) == "r_1"
        ]
        coord_cls = {}
        for d in members:
            c = d["coord_class_max"]
            if c:
                coord_cls[c] = coord_cls.get(c, 0) + 1

        if m_hit_any:
            hyp = "anchored_scale_1to1"
            ev = ("%d/%d anchorable defs have a printed dimension matching a drawn "
                  "distance within 1%%; scale factor 1.0 => drawing unit == dim "
                  "display unit. Unit NAME still not proven by projection alone."
                  % (len(m_hit_any), len(m_anchor)))
        elif m_anchor:
            hyp = "anchor_attempted_no_match"
            ev = ("%d anchorable defs, 0 matched within 1%% => printed dimensions do "
                  "not correspond to any drawn distance in this class" % len(m_anchor))
        else:
            hyp = "ambiguous_no_anchor"
            ev = ("no def in this class carries both a numeric dimension token and a "
                  "LINE; magnitude alone cannot fix the unit")

        hyp_rows.append({
            "span_class": key,
            "label": label,
            "n_defs": len(members),
            "median_span_max": _median([d["bbox_span_max"] for d in members]),
            "n_anchorable": len(m_anchor),
            "n_anchored_any_1pct": len(m_hit_any),
            "n_ratio_1to1": len(m_hit_1to1),
            "coord_class_counts": coord_cls,
            "hypothesis": hyp,
            "evidence": ev,
            "mm_consistent_if_1to1": (
                None if not m_hit_any else
                "median span %.1f drawing units; if unit==mm this is %.3f m"
                % (_median([d["bbox_span_max"] for d in members]),
                   _median([d["bbox_span_max"] for d in members]) / 1000.0)
            ),
        })

    return {
        "schema": SCHEMA,
        "generated_by": "tools/e2/s1_bbox_units.py",
        "card": "S1-C bbox and unit audit",
        "verdict_policy": (
            "MEASUREMENT ONLY - no unit verdict is issued here. S4-C consumes this "
            "table. Hypotheses below are labelled with their supporting counts."
        ),
        "inputs": inputs_meta,
        "bbox_derivability": deriv_block,
        "span_magnitude_classes": span_classes,
        "coordinate_magnitude": coord_block,
        "anchoring": anchor_block,
        "unit_hypothesis_table": hyp_rows,
        "per_def": per_def,
    }


# --- rendering ---------------------------------------------------------------

def _fmt(v, nd=2):
    if v is None:
        return "-"
    if isinstance(v, float):
        if not math.isfinite(v):
            return "-"
        return ("%.*f" % (nd, v)).rstrip("0").rstrip(".") if nd else "%d" % v
    return str(v)


def render_md(rep):
    L = []
    A = L.append
    d = rep["bbox_derivability"]
    a = rep["anchoring"]

    A("# S1-C - bbox and unit audit")
    A("")
    A("Card: **S1-C** (forensic measurement). Schema `%s`." % rep["schema"])
    A("")
    A("> %s" % rep["verdict_policy"])
    A("")
    A("Source: `%s` (%d shard files, %d defs). Generated by `%s`."
      % (rep["inputs"]["glob"], rep["inputs"]["n_shards"], d["n_defs"],
         rep["generated_by"]))
    A("")

    A("## 1. bbox derivability")
    A("")
    A("A bbox is derivable only from LINE start/end: the E1 projection carries")
    A("coordinates on LINE entities and nowhere else (LWPOLYLINE reports only")
    A("`vertices=N`, ARC/CIRCLE/SPLINE/HATCH carry none). So `>=1 LINE` is")
    A("necessary and sufficient for a bbox.")
    A("")
    A("| metric | n | pct |")
    A("|---|---:|---:|")
    A("| defs total | %d | 100%% |" % d["n_defs"])
    A("| bbox derivable (>=1 LINE) | %d | %s%% |"
      % (d["bbox_derivable"], _fmt(d["bbox_derivable_pct"])))
    A("| bbox NOT derivable (0 LINE) | %d | %s%% |"
      % (d["bbox_not_derivable"], _fmt(_pct(d["bbox_not_derivable"], d["n_defs"]))))
    A("| degenerate span (max span == 0) | %d | - |" % d["degenerate_span_zero"])
    A("| sample truncated (entity_count > 30 sampled) | %d | - |"
      % d["sample_truncated_defs"])
    A("| LINE in dxf histogram but none sampled | %d | - |"
      % d["line_declared_but_none_sampled"])
    A("")
    A("**Projection self-consistency**: declared-bbox present AND derivable = %d; "
      "declared-bbox absent AND not derivable = %d; declared-vs-recomputed "
      "mismatch = %d of %d checked."
      % (d["declared_present_and_derivable"], d["declared_absent_and_not_derivable"],
         d["declared_vs_calc_mismatch"], d["declared_vs_calc_checked"]))
    A("")
    A("Entity kinds inside the %d non-derivable defs: %s"
      % (d["bbox_not_derivable"],
         ", ".join("%s=%d" % kv for kv in
                   list(d["nonderivable_kind_totals"].items())[:12]) or "-"))
    A("")

    A("## 2. bbox span magnitude class")
    A("")
    A("Class assigned on `max(span_x, span_y)` of the recomputed bbox, over the")
    A("%d derivable defs." % d["bbox_derivable"])
    A("")
    A("| class | n defs | pct of derivable | median span | min | max |")
    A("|---|---:|---:|---:|---:|---:|")
    for key, _lo, _hi, label in MAG_CLASSES:
        c = rep["span_magnitude_classes"][key]
        A("| %s | %d | %s | %s | %s | %s |"
          % (label, c["n_defs"], _fmt(c["pct_of_derivable"]),
             _fmt(c["median_span_max"]), _fmt(c["min_span_max"]),
             _fmt(c["max_span_max"])))
    A("")

    A("## 3. coordinate magnitude distribution")
    A("")
    cm = rep["coordinate_magnitude"]
    A("Basis: %s. n=%d defs." % (cm["basis"], cm["n_defs_with_coords"]))
    A("")
    A("| class | n defs |")
    A("|---|---:|")
    for key, _lo, _hi, label in MAG_CLASSES:
        A("| %s | %d |" % (label, cm["class_counts"][key]))
    A("")
    A("median per-def max|coord| = %s; range [%s, %s]."
      % (_fmt(cm["median_abs_max"]), _fmt(cm["min_abs_max"]), _fmt(cm["max_abs_max"])))
    A("")
    A("Coordinate magnitude and span magnitude are independent axes: a small")
    A("block can sit far from the origin. Read them together, not either alone.")
    A("")

    A("## 4. numeric text tokens vs LINE spans (unit anchoring)")
    A("")
    A("Dimension candidates are pure-numeric MTEXT bodies after stripping inline")
    A("format codes (`\\A1;3280` -> `3280`). %s"
      % a["label_exclusion_note"])
    A("")
    A("| metric | n | pct of anchorable |")
    A("|---|---:|---:|")
    A("| defs with >=1 dim candidate | %d | - |" % a["n_defs_with_dim_candidates"])
    A("| anchorable (dim candidate AND >=1 LINE) | %d | 100%% |" % a["n_defs_anchorable"])
    A("| **numeric text == a LINE span within 1%% (card metric)** | **%d** | **%s%%** |"
      % (a["card_primary_metric"]["n_hit"], _fmt(a["card_primary_metric"]["pct"])))
    A("| numeric text == a LINE axis dx/dy within 1%% | %d | %s%% |"
      % (a["line_axis_1pct"]["n_hit"], _fmt(a["line_axis_1pct"]["pct"])))
    A("| numeric text == bbox X/Y span within 1%% | %d | %s%% |"
      % (a["bbox_span_1pct"]["n_hit"], _fmt(a["bbox_span_1pct"]["pct"])))
    A("| any of the above | %d | %s%% |"
      % (a["any_1pct"]["n_hit"], _fmt(a["any_1pct"]["pct"])))
    A("")
    A("### Why the card metric under-reads, and what to use instead")
    A("")
    A("The card asks for `numeric text == a LINE span`. That is reported above as")
    A("the primary metric. It is a **floor, not the anchoring rate**: in a")
    A("dimension-cache block the dimension LINE is drawn *inset* from the two")
    A("extension lines, so the printed value never equals the dim-line span, but")
    A("does equal the extension-line separation = the bbox span. Worked example,")
    A("def `*D295`: extension lines span 1660 each, dim line spans 3160, MTEXT")
    A("reads 3280, bbox X span = 3280. Exact match on bbox, no match on any LINE.")
    A("That is why the bbox row is the one S4-C should treat as the anchoring")
    A("rate, with the card metric kept as the conservative lower bound.")
    A("")
    A("### Best-ratio buckets (numeric token / nearest drawn distance)")
    A("")
    A("A ratio of 1.0 means the drawing unit and the printed dimension unit are")
    A("the same; 25.4 would mean inches printed over mm geometry, etc.")
    A("")
    A("| bucket | vs LINE span | vs bbox span |")
    A("|---|---:|---:|")
    keys = list(dict.fromkeys(
        list(a["best_ratio_buckets_vs_line_span"].keys())
        + list(a["best_ratio_buckets_vs_bbox_span"].keys())))
    order = [k for k, _t, _l in RATIO_BUCKETS] + ["other"]
    for k in [x for x in order if x in keys]:
        lab = a["ratio_bucket_labels"].get(k, k)
        A("| %s | %d | %d |"
          % (lab, a["best_ratio_buckets_vs_line_span"].get(k, 0),
             a["best_ratio_buckets_vs_bbox_span"].get(k, 0)))
    A("")

    A("## 5. Unit hypothesis table (per span magnitude class)")
    A("")
    A("**This is the table S4-C consumes.** No verdict is issued here.")
    A("")
    A("| span class | n defs | median span | anchorable | anchored @1% | ratio 1:1 | hypothesis |")
    A("|---|---:|---:|---:|---:|---:|---|")
    for r in rep["unit_hypothesis_table"]:
        if r["n_defs"] == 0:
            A("| %s | 0 | - | - | - | - | %s |" % (r["label"], r["hypothesis"]))
            continue
        A("| %s | %d | %s | %d | %d | %d | `%s` |"
          % (r["label"], r["n_defs"], _fmt(r["median_span_max"]), r["n_anchorable"],
             r["n_anchored_any_1pct"], r["n_ratio_1to1"], r["hypothesis"]))
    A("")
    A("Per-class evidence:")
    A("")
    for r in rep["unit_hypothesis_table"]:
        if r["n_defs"] == 0:
            continue
        A("- **%s** (`%s`): %s" % (r["label"], r["hypothesis"], r["evidence"]))
        if r.get("mm_consistent_if_1to1"):
            A("  - mm reading: %s" % r["mm_consistent_if_1to1"])
    A("")
    A("### What the anchoring evidence does and does not establish")
    A("")
    A("**Established by measurement**: where a printed dimension matches a drawn")
    A("distance at ratio 1.0, the geometry is stored in the same unit the")
    A("dimension text displays. The scale factor is 1.0, not 25.4 / 304.8 / 1000.")
    A("")
    A("**NOT established**: the *name* of that unit. The projection carries no")
    A("$INSUNITS / $MEASUREMENT header and no DIMSCALE. A span of 3280 units is")
    A("consistent with mm (3.28 m, a plausible room dimension) and that is the")
    A("leading hypothesis on magnitude plausibility alone -- but magnitude")
    A("plausibility is an argument, not a header read. Confirming the unit name")
    A("requires $INSUNITS from the source DWG, which is outside this projection.")
    A("")
    A("**Ambiguous by construction**: defs with no numeric dimension token have no")
    A("internal anchor at all. Their unit can only be inherited from the drawing")
    A("they belong to, never derived from the projection.")
    A("")
    return "\n".join(L) + "\n"


# --- IO ----------------------------------------------------------------------

def _relpath(path, start=REPO):
    """relpath, but tolerant of a different drive (selftest runs out of %TEMP%)."""
    try:
        return os.path.relpath(path, start).replace("\\", "/")
    except ValueError:
        return os.path.abspath(path).replace("\\", "/")


def load_shards(pattern):
    paths = sorted(glob.glob(pattern))
    recs = []
    bad = 0
    for p in paths:
        with open(p, "r", encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except json.JSONDecodeError:
                    bad += 1
                    continue
                if not isinstance(r, dict) or "prompt" not in r:
                    bad += 1
                    continue
                recs.append((os.path.basename(p), r))
    return paths, recs, bad


def run(pattern, out_json, out_md, quiet=False):
    paths, recs, bad = load_shards(pattern)
    per_def = []
    for shard, r in recs:
        try:
            parsed = parse_projection(r.get("prompt") or "")
            m = measure_def(parsed, r.get("unit_id"))
        except Exception as exc:  # never crash the RUN on one bad def
            m = {
                "unit_id": r.get("unit_id"), "def_name": None,
                "bbox_derivable": False, "anchorable": False,
                "parse_issues": ["EXCEPTION: %s: %s" % (type(exc).__name__, exc)],
                "kind_hist": {}, "n_dim_candidates": 0, "n_label_embedded": 0,
                "bbox_span_class": None, "coord_class_max": None,
                "n_line_declared": 0, "n_line_sampled": 0,
                "sample_truncated": False, "bbox_declared_present": False,
                "bbox_declared_matches_calc": None, "degenerate_span": None,
                "bbox_span_max": None, "coord_abs_max": None,
                "anchor": {"line_span_1pct": False, "line_axis_1pct": False,
                           "bbox_span_1pct": False, "any_1pct": False,
                           "best_ratio_vs_line_span": None,
                           "best_ratio_vs_bbox_span": None, "matches": []},
            }
        m["shard"] = shard
        per_def.append(m)

    inputs_meta = {
        "glob": _relpath(pattern),
        "n_shards": len(paths),
        "shards": [os.path.basename(p) for p in paths],
        "n_records": len(recs),
        "n_unparsable_lines": bad,
    }
    rep = aggregate(per_def, inputs_meta)

    for path, blob in ((out_json, json.dumps(rep, indent=2, ensure_ascii=False)),
                       (out_md, render_md(rep))):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(blob)

    if not quiet:
        d = rep["bbox_derivability"]
        a = rep["anchoring"]
        print("shards=%d defs=%d unparsable=%d" % (len(paths), len(recs), bad))
        print("bbox derivable: %d/%d (%.1f%%)  not derivable: %d"
              % (d["bbox_derivable"], d["n_defs"], d["bbox_derivable_pct"] or 0,
                 d["bbox_not_derivable"]))
        print("declared-vs-recomputed bbox mismatches: %d/%d"
              % (d["declared_vs_calc_mismatch"], d["declared_vs_calc_checked"]))
        print("anchorable defs: %d" % a["n_defs_anchorable"])
        print("  card metric (text==LINE span @1%%): %d (%.1f%%)"
              % (a["card_primary_metric"]["n_hit"], a["card_primary_metric"]["pct"] or 0))
        print("  text==bbox span @1%%:               %d (%.1f%%)"
              % (a["bbox_span_1pct"]["n_hit"], a["bbox_span_1pct"]["pct"] or 0))
        print("wrote %s" % _relpath(out_json))
        print("wrote %s" % _relpath(out_md))
    return rep


# --- selftest ----------------------------------------------------------------

FIX_ANCHORED = """DWG block definition annotation task
Definition name: *FIX_DIM
entity_count: 6
dxf_name histogram: INSERT=2, LINE=3, MTEXT=1
layer histogram: DIM=6
bbox from LINE start/end: [1000.0, 500.0, 0, 4280.0, 2160.0, 0]
sampled entities (max 30):
- LINE layer=DIM handle=A1 (1000.0,2160.0)->(1000.0,500.0)
- LINE layer=DIM handle=A2 (4280.0,2160.0)->(4280.0,500.0)
- LINE layer=DIM handle=A3 (1060.0,700.0)->(4220.0,700.0)
- INSERT layer=DIM handle=A4 block=DIMDOT
- MTEXT layer=DIM handle=A5 '\\A1;3280'
- POINT layer=DEFPOINTS handle=A6
"""

FIX_NOLINE = """Definition name: *FIX_NOLINE
entity_count: 4
dxf_name histogram: LWPOLYLINE=2, HATCH=1, ARC=1
layer histogram: X-WALL=4
bbox from LINE start/end: (not derivable from LINE start/end)
sampled entities (max 30):
- LWPOLYLINE layer=X-WALL handle=B1 vertices=5
- LWPOLYLINE layer=X-WALL handle=B2 vertices=9
- HATCH layer=X-WALL handle=B3 pattern=SOLID loops=2
- ARC layer=X-WALL handle=B4
"""

FIX_GARBAGE = """Definition name: *FIX_JUNK
entity_count: 5
dxf_name histogram: LINE=1
layer histogram: 0=5
bbox from LINE start/end: [0.0, 0.0, 0, 5.0, 0.0, 0]
sampled entities (max 30):
- LINE layer=0 handle=C1 (0.0,0.0)->(5.0,0.0)
- FROBNICATOR layer=0 handle=C2 whatever=1
- LINE layer=0 handle=C3 (garbled coords here
-
- TEXT layer=DEFPOINTS handle=C4 '(84A+84B+84C)45F'
"""

FIX_TRUNC = """Definition name: *FIX_TRUNC
entity_count: 400
dxf_name histogram: LINE=400
layer histogram: X-WALL=400
bbox from LINE start/end: [0.0, 0.0, 0, 2000000.0, 3.0, 0]
sampled entities (max 30):
- LINE layer=X-WALL handle=D1 (0.0,0.0)->(1.0,3.0)
- LINE layer=X-WALL handle=D2 (0.0,0.0)->(2.0,1.0)
"""

FIX_NONPLANAR = """Definition name: *FIX_NONPLANAR
entity_count: 2
dxf_name histogram: LINE=2
layer histogram: FUR=2
bbox from LINE start/end: [-880, -132, -0.006, 40, 20, 0]
sampled entities (max 30):
- LINE layer=FUR handle=F1 (-880,-132)->(40,20)
- LINE layer=FUR handle=F2 (-880,20)->(40,-132)
"""

FIX_INCH = """Definition name: *FIX_INCH
entity_count: 3
dxf_name histogram: LINE=2, MTEXT=1
layer histogram: DIM=3
bbox from LINE start/end: [0.0, 0.0, 0, 2540.0, 0.0, 0]
sampled entities (max 30):
- LINE layer=DIM handle=E1 (0.0,0.0)->(2540.0,0.0)
- LINE layer=DIM handle=E2 (0.0,0.0)->(0.0,0.0)
- MTEXT layer=DIM handle=E3 '\\A1;100'
"""


_RAN = []


def _chk(name, got, want, fails):
    ok = got == want
    _RAN.append(name)
    print("  [%s] %-46s got=%r want=%r" % ("PASS" if ok else "FAIL", name, got, want))
    if not ok:
        fails.append(name)
    return ok


def selftest():
    print("=== S1-C selftest: parser unit checks ===")
    del _RAN[:]
    fails = []

    # --- parse_entity: every grammar shape from the card ---
    e = parse_entity("- LINE layer=DIM handle=8B52 (44248.83,24580.207)->(44248.83,22920.207)")
    _chk("LINE.kind", e["kind"], "LINE", fails)
    _chk("LINE.handle", e["handle"], "8B52", fails)
    _chk("LINE.coords", e["coords"], (44248.83, 24580.207, 44248.83, 22920.207), fails)
    _chk("INSERT.kind", parse_entity("- INSERT layer=DIM handle=8B55 block=DIMDOT")["kind"], "INSERT", fails)
    _chk("MTEXT.text", parse_entity("- MTEXT layer=DIM handle=8B57 '\\A1;3280'")["text"], "\\A1;3280", fails)
    _chk("POINT.kind", parse_entity("- POINT layer=DEFPOINTS handle=8B58")["kind"], "POINT", fails)
    _chk("LWPOLY.verts", parse_entity("- LWPOLYLINE layer=X-... handle=4376 vertices=5")["vertices"], 5, fails)
    _chk("LWPOLY.nocoords", parse_entity("- LWPOLYLINE layer=X-... handle=4376 vertices=5")["coords"], None, fails)
    _chk("WIPEOUT.kind", parse_entity("- WIPEOUT layer=0 handle=4855")["kind"], "WIPEOUT", fails)
    _chk("SPLINE.kind", parse_entity("- SPLINE layer=... handle=1BCC")["kind"], "SPLINE", fails)
    _chk("HATCH.kind", parse_entity("- HATCH layer=... handle=1BCE pattern=SOLID loops=2")["kind"], "HATCH", fails)
    _chk("TEXT.text", parse_entity("- TEXT layer=DEFPOINTS handle=3AE '101 dong'")["text"], "101 dong", fails)
    _chk("ARC.kind", parse_entity("- ARC layer=... handle=820F")["kind"], "ARC", fails)
    _chk("CIRCLE.radius", parse_entity("- CIRCLE layer=... handle=3288 radius=81")["radius"], 81.0, fails)
    _chk("ELLIPSE.kind", parse_entity("- ELLIPSE layer=... handle=6B10")["kind"], "ELLIPSE", fails)
    _chk("3DFACE.kind", parse_entity("- 3DFACE layer=... handle=1DA2")["kind"], "3DFACE", fails)

    # --- unknown shapes degrade, never crash ---
    _chk("unknown->other", parse_entity("- FROBNICATOR layer=0 handle=C2 x=1")["kind"], "other", fails)
    _chk("empty->other", parse_entity("- ")["kind"], "other", fails)
    _chk("garbage->other", parse_entity("!!! not an entity !!!")["kind"], "other", fails)
    _chk("truncated_coords", parse_entity("- LINE layer=0 handle=C3 (garbled coords here")["coords"], None, fails)

    # --- mtext code stripping ---
    _chk("strip \\A1;", strip_mtext_codes("\\A1;3280"), "3280", fails)
    _chk("strip nested", strip_mtext_codes("{\\W0.8;\\A1;1420}"), "1420", fails)
    _chk("strip keeps label", strip_mtext_codes("84A"), "84A", fails)

    # --- magnitude classes incl. boundaries ---
    _chk("mag 9.99", mag_class(9.99), "lt_10", fails)
    _chk("mag 10 (boundary)", mag_class(10.0), "10_1e2", fails)
    _chk("mag 99.9", mag_class(99.9), "10_1e2", fails)
    _chk("mag 100 (boundary)", mag_class(100.0), "1e2_1e4", fails)
    _chk("mag 3280", mag_class(3280.0), "1e2_1e4", fails)
    _chk("mag 1e4 (boundary)", mag_class(1e4), "1e4_1e6", fails)
    _chk("mag 44248", mag_class(44248.83), "1e4_1e6", fails)
    _chk("mag 1e6 (boundary)", mag_class(1e6), "ge_1e6", fails)
    _chk("mag 1e9", mag_class(1e9), "ge_1e6", fails)
    _chk("mag negative uses abs", mag_class(-44248.0), "1e4_1e6", fails)
    _chk("mag None", mag_class(None), None, fails)

    # --- ratio buckets ---
    _chk("ratio 1.0", ratio_bucket(1.0), "r_1", fails)
    _chk("ratio 1.005 (in 1%)", ratio_bucket(1.005), "r_1", fails)
    _chk("ratio 1.5", ratio_bucket(1.5), "other", fails)
    _chk("ratio 25.4", ratio_bucket(25.4), "r_25_4", fails)
    _chk("ratio 1000", ratio_bucket(1000.0), "r_1000", fails)

    print("\n=== S1-C selftest: end-to-end on in-code fixture ===")
    recs = [
        {"kind": "def_annotation", "prompt": FIX_ANCHORED, "unit_id": "fix-anchored"},
        {"kind": "def_annotation", "prompt": FIX_NOLINE, "unit_id": "fix-noline"},
        {"kind": "def_annotation", "prompt": FIX_GARBAGE, "unit_id": "fix-junk"},
        {"kind": "def_annotation", "prompt": FIX_TRUNC, "unit_id": "fix-trunc"},
        {"kind": "def_annotation", "prompt": FIX_INCH, "unit_id": "fix-inch"},
        {"kind": "def_annotation", "prompt": FIX_NONPLANAR, "unit_id": "fix-nonplanar"},
    ]
    tmp = tempfile.mkdtemp(prefix="s1c_selftest_")
    shard = os.path.join(tmp, "shard_99.jsonl")
    with open(shard, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        fh.write("\n")                      # blank line tolerated
        fh.write("{not json at all\n")      # unparsable line tolerated
    rep = run(os.path.join(tmp, "shard_*.jsonl"),
              os.path.join(tmp, "out.json"), os.path.join(tmp, "out.md"), quiet=True)

    d = rep["bbox_derivability"]
    a = rep["anchoring"]
    by = {p["unit_id"]: p for p in rep["per_def"]}

    _chk("fixture defs parsed", d["n_defs"], 6, fails)
    _chk("bad jsonl line counted", rep["inputs"]["n_unparsable_lines"], 1, fails)
    _chk("derivable count", d["bbox_derivable"], 5, fails)
    _chk("not-derivable count", d["bbox_not_derivable"], 1, fails)
    _chk("noline is not derivable", by["fix-noline"]["bbox_derivable"], False, fails)
    _chk("noline declared absent", by["fix-noline"]["bbox_declared_present"], False, fails)
    _chk("derivable agrees with declared", d["derivable_vs_declared_disagree"], 0, fails)
    _chk("junk def survives", by["fix-junk"]["bbox_derivable"], True, fails)
    _chk("junk 'other' kind captured", by["fix-junk"]["other_kind_tokens"], ["FROBNICATOR"], fails)
    _chk("junk garbled LINE dropped", by["fix-junk"]["n_line_spans"], 1, fails)

    # anchored fixture: MTEXT 3280 == bbox X span, != any LINE span (1660/1660/3160)
    an = by["fix-anchored"]
    _chk("anchored dim candidates", an["n_dim_candidates"], 1, fails)
    _chk("anchored bbox span x", an["bbox_span_x"], 3280.0, fails)
    _chk("anchored NOT line-span match", an["anchor"]["line_span_1pct"], False, fails)
    _chk("anchored IS bbox-span match", an["anchor"]["bbox_span_1pct"], True, fails)
    _chk("anchored ratio vs bbox == 1", an["anchor"]["best_ratio_vs_bbox_span"], 1.0, fails)
    _chk("anchored span class", an["bbox_span_class"], "1e2_1e4", fails)
    _chk("anchored declared==calc", an["bbox_declared_matches_calc"], True, fails)

    # label digits must NOT become dimension candidates
    jk = by["fix-junk"]
    _chk("label digits excluded", jk["n_dim_candidates"], 0, fails)
    _chk("label digits counted", jk["n_label_embedded"], 4, fails)

    # truncation + declared/calc divergence detected
    tr = by["fix-trunc"]
    _chk("trunc flagged", tr["sample_truncated"], True, fails)
    _chk("trunc declared!=calc", tr["bbox_declared_matches_calc"], False, fails)
    _chk("trunc mismatch surfaced", d["declared_vs_calc_mismatch"], 1, fails)

    # unit-mismatch fixture: 100 printed over 2540 drawn -> 25.4x
    ih = by["fix-inch"]
    _chk("inch ratio bucket", ratio_bucket(1.0 / ih["anchor"]["best_ratio_vs_line_span"]), "r_25_4", fails)
    _chk("inch not 1pct anchored", ih["anchor"]["line_span_1pct"], False, fails)

    # hypothesis table shape
    _chk("hyp table rows", len(rep["unit_hypothesis_table"]), len(MAG_CLASSES), fails)
    hyp = {r["span_class"]: r["hypothesis"] for r in rep["unit_hypothesis_table"]}
    _chk("hyp lt_10 anchored", hyp["lt_10"], "ambiguous_no_anchor", fails)
    _chk("hyp 1e2_1e4 anchored", hyp["1e2_1e4"], "anchored_scale_1to1", fails)
    _chk("hyp ge_1e6 no data", hyp["ge_1e6"], "no_data", fails)

    # outputs are real files
    _chk("json written", os.path.getsize(os.path.join(tmp, "out.json")) > 0, True, fails)
    _chk("md written", os.path.getsize(os.path.join(tmp, "out.md")) > 0, True, fails)
    json.loads(open(os.path.join(tmp, "out.json"), encoding="utf-8").read())
    print("  [PASS] out.json reparses as valid JSON")

    print("\n=== selftest: %d checks, %d failed ===" % (len(_RAN), len(fails)))
    print("SELFTEST: %s" % ("PASS" if not fails else "FAIL -> " + ", ".join(fails)))
    return 0 if not fails else 1


def main():
    ap = argparse.ArgumentParser(description="S1-C bbox + unit audit")
    ap.add_argument("--selftest", action="store_true", help="run self-contained checks")
    ap.add_argument("--shards", default=SHARD_GLOB)
    ap.add_argument("--out-json", default=OUT_JSON)
    ap.add_argument("--out-md", default=OUT_MD)
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    run(args.shards, args.out_json, args.out_md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
