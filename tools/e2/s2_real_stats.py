#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S2-A real-corpus wall statistics extractor (deterministic).

The fidelity yardstick for the E2 synthetic generator. Reads E1 shard
projections (LINE coords only -- projections carry NO polyline geometry) plus
the annot_v1 judge annotations, and emits three distributions:

  1. thickness_hist      -- parallel LINE-pair spacing histogram (candidate
                            thickness bands) per layer-token class.
  2. entity_mix_by_role   -- entity-type mix aggregated per def role, using
                            opus48_max as the reference judge.
  3. layer_tokens         -- layer-token frequency table ($ + non-alnum split).

Output: reports/e2/s2/real_stats.{json,md}. The JSON is the S2-F comparator's
input. Stdlib only. Deterministic (sorted keys, fixed bin edges, no timestamp).

Usage:
  python s2_real_stats.py                 # run on repo defaults, write outputs
  python s2_real_stats.py --selftest      # self-contained fixture + assertions
"""

from __future__ import annotations

import argparse
import bisect
import glob
import json
import math
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

STATS_SCHEMA = "rs.v1"

# Reference judge for the role join (per card).
REFERENCE_JUDGE = "opus48_max"
ALL_JUDGES = ("opus48_max", "fable5_high", "sol56_xhigh", "sonnet5_xhigh", "grok45_xhigh")

# Parallel-pair parameters (per card): angle tol 2deg, overlap ratio >= 0.3.
ANGLE_TOL_DEG = 2.0
MIN_OVERLAP = 0.3

# Fixed histogram edges (drawing units, ~mm). Fine at door/wall scale, coarse
# for room/building spans. Values >= last edge are clamped into the last bin.
# 26 edges -> 25 bins. Kept stable so real and synthetic share the same bins.
BIN_EDGES = [
    0, 1, 2, 5, 10, 25, 50, 75, 100, 125, 150, 175, 200, 250, 300,
    400, 500, 750, 1000, 1500, 2500, 5000, 10000, 20000, 50000, 300000,
]

LAYER_CLASSES = ("WALL", "DOOR", "DIM", "other")

# --------------------------------------------------------------------------
# Projection parsing
# --------------------------------------------------------------------------

_DEF_NAME = re.compile(r"^Definition name:\s*(.+?)\s*$")
_ENTITY_COUNT = re.compile(r"^entity_count:\s*(\d+)\s*$")
_DXF_HIST = re.compile(r"^dxf_name histogram:\s*(.*)$")
_LAYER_HIST = re.compile(r"^layer histogram:\s*(.*)$")
# entity line: "- LINE layer=DIM handle=8B52 (x0,y0)->(x1,y1)"
_ENT_LINE = re.compile(r"^-\s+([0-9A-Za-z]+)\s+layer=(.+?)\s+handle=(\S+)(.*)$")
_LINE_COORDS = re.compile(
    r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)"
    r"\s*->\s*"
    r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)"
)


def _parse_kv_hist(text):
    """Parse 'A=1, B=2' into {'A':1,'B':2}. Unknown shapes are skipped."""
    out = {}
    for part in text.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, cnt = part.rpartition("=")
        name = name.strip()
        try:
            out[name] = int(cnt.strip())
        except ValueError:
            continue
    return out


def parse_projection(prompt):
    """Parse one def_annotation projection prompt.

    Returns a dict with def_name, entity_count, dxf_hist, layer_hist, and the
    sampled entity list (LINE entities carry parsed start/end coords). Lines
    that do not match any known shape are tagged kind='other' and never crash.
    Returns None if the prompt has no 'Definition name:' header.
    """
    def_name = None
    entity_count = None
    dxf_hist = {}
    layer_hist = {}
    sampled = []
    in_sampled = False

    for raw in prompt.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if in_sampled:
            if stripped.startswith("- "):
                m = _ENT_LINE.match(stripped)
                if not m:
                    sampled.append({"kind": "other", "raw": stripped})
                    continue
                etype, layer, handle, rest = m.groups()
                ent = {"kind": etype, "layer": layer, "handle": handle}
                if etype == "LINE":
                    cm = _LINE_COORDS.search(rest)
                    if cm:
                        x0, y0, x1, y1 = (float(v) for v in cm.groups())
                        ent["start"] = (x0, y0)
                        ent["end"] = (x1, y1)
                sampled.append(ent)
                continue
            # Blank line inside the sampled block is tolerated; any other
            # non-bullet line ends the block (e.g. the Instructions section).
            if stripped == "":
                continue
            in_sampled = False
            # fall through to header matching for this line

        if def_name is None:
            m = _DEF_NAME.match(stripped)
            if m:
                def_name = m.group(1)
                continue
        m = _ENTITY_COUNT.match(stripped)
        if m:
            entity_count = int(m.group(1))
            continue
        m = _DXF_HIST.match(stripped)
        if m:
            dxf_hist = _parse_kv_hist(m.group(1))
            continue
        m = _LAYER_HIST.match(stripped)
        if m:
            layer_hist = _parse_kv_hist(m.group(1))
            continue
        if stripped.startswith("sampled entities"):
            in_sampled = True
            continue

    if def_name is None:
        return None
    return {
        "def_name": def_name,
        "entity_count": entity_count,
        "dxf_hist": dxf_hist,
        "layer_hist": layer_hist,
        "sampled": sampled,
    }


# --------------------------------------------------------------------------
# Layer classification / tokenization
# --------------------------------------------------------------------------

_TOKEN = re.compile(r"[0-9A-Za-z가-힣]+")  # alnum + Hangul syllables
_WALL_TOK = re.compile(r"^W\d*$")


def tokenize_layer(layer):
    """Split a layer name on '$' separators and non-alnum into tokens.

    Hangul syllables count as alphanumeric. '$' is treated as a separator like
    any other non-alnum char, so '.../$W1' -> [...,'W1']."""
    if not isinstance(layer, str):
        return []
    return _TOKEN.findall(layer)


def classify_layer(layer):
    """Coarse layer-token class: WALL / DOOR / DIM / other.

    Rules (ordered): a DIM/DEFPOINTS token -> DIM; a DOOR token -> DOOR; a
    wall-family token (W, W<n>, or contains 'WALL') -> WALL; else other.
    Narrow by design: WALL here means the LINE sits on a wall-family layer, not
    that the pair spacing is itself a wall thickness (see real_stats.md)."""
    if not isinstance(layer, str):
        return "other"
    toks = [t.upper() for t in tokenize_layer(layer)]
    if not toks:
        return "other"
    if "DIM" in toks or "DEFPOINTS" in toks:
        return "DIM"
    if any("DOOR" in t for t in toks):
        return "DOOR"
    if any(_WALL_TOK.match(t) or "WALL" in t for t in toks):
        return "WALL"
    return "other"


# --------------------------------------------------------------------------
# Parallel-pair geometry (reused from E1 wall_pairs.py convention)
# --------------------------------------------------------------------------

def _angle_mod_pi(dx, dy):
    return math.atan2(dy, dx) % math.pi


def _angle_diff(a, b):
    d = abs(a - b)
    return min(d, math.pi - d)


def _line_record(ent):
    """Build a geometric line record from a parsed LINE entity, or None."""
    if ent.get("kind") != "LINE" or "start" not in ent or "end" not in ent:
        return None
    (x0, y0), (x1, y1) = ent["start"], ent["end"]
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length <= 0.0:
        return None
    return {
        "handle": ent.get("handle"),
        "layer": ent.get("layer"),
        "start": (x0, y0),
        "end": (x1, y1),
        "dx": dx,
        "dy": dy,
        "len": length,
        "angle": _angle_mod_pi(dx, dy),
    }


def _gap_and_overlap(a, b):
    """Perpendicular spacing (gap) and projection-overlap ratio for two lines.

    Gap = distance from the shorter segment's midpoint to the longer line.
    Overlap ratio = overlapped projection length / shorter segment length."""
    longer, shorter = (a, b) if a["len"] >= b["len"] else (b, a)
    ux = longer["dx"] / longer["len"]
    uy = longer["dy"] / longer["len"]
    sx = (shorter["start"][0] + shorter["end"][0]) * 0.5
    sy = (shorter["start"][1] + shorter["end"][1]) * 0.5
    gap = abs((sx - longer["start"][0]) * uy - (sy - longer["start"][1]) * ux)

    def project(p):
        return (p[0] - longer["start"][0]) * ux + (p[1] - longer["start"][1]) * uy

    lo_a, lo_b = 0.0, longer["len"]
    sh_a, sh_b = sorted((project(shorter["start"]), project(shorter["end"])))
    overlap = max(0.0, min(lo_b, sh_b) - max(lo_a, sh_a))
    return gap, overlap / shorter["len"]


def parallel_pairs(entities, angle_tol_rad, min_overlap):
    """Yield (handle_a, handle_b, gap, class) for near-parallel LINE pairs
    within a single definition (all-pairs; sampled entities are <=30 per def).

    class = shared layer class if both lines agree, else 'other'."""
    lines = [r for r in (_line_record(e) for e in entities) if r is not None]
    out = []
    for i in range(len(lines)):
        li = lines[i]
        ci = classify_layer(li["layer"])
        for j in range(i + 1, len(lines)):
            lj = lines[j]
            if _angle_diff(li["angle"], lj["angle"]) > angle_tol_rad:
                continue
            gap, overlap = _gap_and_overlap(li, lj)
            if overlap < min_overlap or gap <= 0.0:
                continue
            cj = classify_layer(lj["layer"])
            cls = ci if ci == cj else "other"
            out.append((li["handle"], lj["handle"], gap, cls))
    return out


def _histogram(values, edges):
    """Bin values into len(edges)-1 counts; values >= last edge clamp to last."""
    counts = [0] * (len(edges) - 1)
    last = len(counts) - 1
    for v in values:
        # rightmost bin index whose left edge <= v
        idx = bisect.bisect_right(edges, v) - 1
        if idx < 0:
            idx = 0
        elif idx > last:
            idx = last
        counts[idx] += 1
    return counts


def _top_bands(counts, edges, top_n=3):
    """Return the top-N populated bins as {range:[lo,hi], count:n}, count desc."""
    ranked = sorted(
        (i for i, c in enumerate(counts) if c > 0),
        key=lambda i: (-counts[i], i),
    )
    return [
        {"range": [edges[i], edges[i + 1]], "count": counts[i]}
        for i in ranked[:top_n]
    ]


# --------------------------------------------------------------------------
# Judge loading
# --------------------------------------------------------------------------

def _extract_handle(item):
    """wall_line_handles item is a str OR {'handle':..,'reason':..}. Handle both."""
    if isinstance(item, str):
        h = item.strip()
        return h or None
    if isinstance(item, dict):
        h = item.get("handle")
        if isinstance(h, str) and h.strip():
            return h.strip()
    return None


def load_judges(judge_root):
    """Return (roles_by_unit, wall_handles_by_unit).

    roles_by_unit uses the reference judge (opus48_max). wall_handles_by_unit is
    the union of wall_line_handles across ALL judges (per unit_id)."""
    roles_by_unit = {}
    wall_handles = defaultdict(set)

    ref_dir = os.path.join(judge_root, REFERENCE_JUDGE)
    for f in sorted(glob.glob(os.path.join(ref_dir, "shard_*.json"))):
        with open(f, encoding="utf-8") as fh:
            for rec in json.load(fh):
                uid = rec.get("unit_id")
                if uid is not None:
                    roles_by_unit[uid] = rec.get("role")

    for judge in ALL_JUDGES:
        jdir = os.path.join(judge_root, judge)
        for f in sorted(glob.glob(os.path.join(jdir, "shard_*.json"))):
            with open(f, encoding="utf-8") as fh:
                for rec in json.load(fh):
                    uid = rec.get("unit_id")
                    if uid is None:
                        continue
                    for item in (rec.get("wall_line_handles") or []):
                        h = _extract_handle(item)
                        if h:
                            wall_handles[uid].add(h)
    return roles_by_unit, dict(wall_handles)


def iter_shard_records(shards_dir):
    """Yield parsed shard records: (unit_id, projection dict)."""
    for f in sorted(glob.glob(os.path.join(shards_dir, "shard_*.jsonl"))):
        with open(f, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rec = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                prompt = rec.get("prompt")
                if not isinstance(prompt, str):
                    continue
                proj = parse_projection(prompt)
                if proj is None:
                    continue
                yield rec.get("unit_id"), proj


# --------------------------------------------------------------------------
# Stats builder
# --------------------------------------------------------------------------

def build_stats(shards_dir, judge_root):
    angle_tol = math.radians(ANGLE_TOL_DEG)
    roles_by_unit, wall_handles = load_judges(judge_root)

    # thickness: gaps by class (all pairs) and the judge-wall-confirmed subset.
    gaps_by_class = {c: [] for c in LAYER_CLASSES}
    gaps_conf_by_class = {c: [] for c in LAYER_CLASSES}

    # entity mix by role (dxf_name histogram is the authoritative full mix).
    role_entity = defaultdict(Counter)
    role_defs = Counter()
    role_total_entities = Counter()

    # layer token frequency (weighted by entity counts from layer histogram).
    token_freq = Counter()
    layer_freq = Counter()

    n_units = 0
    n_units_with_role = 0
    n_defs_with_2plus_lines = 0

    for unit_id, proj in iter_shard_records(shards_dir):
        n_units += 1

        # --- entity mix by role ---
        role = roles_by_unit.get(unit_id)
        role_key = role if role is not None else "__unjudged__"
        if role is not None:
            n_units_with_role += 1
        role_defs[role_key] += 1
        for etype, cnt in proj["dxf_hist"].items():
            role_entity[role_key][etype] += cnt
            role_total_entities[role_key] += cnt

        # --- layer tokens (weighted by entity count on the layer) ---
        for layer, cnt in proj["layer_hist"].items():
            layer_freq[layer] += cnt
            for tok in set(tokenize_layer(layer)):
                token_freq[tok] += cnt

        # --- thickness histogram ---
        lines = [e for e in proj["sampled"] if e.get("kind") == "LINE" and "start" in e]
        if len(lines) >= 2:
            n_defs_with_2plus_lines += 1
        wall_set = wall_handles.get(unit_id, set())
        for ha, hb, gap, cls in parallel_pairs(proj["sampled"], angle_tol, MIN_OVERLAP):
            gaps_by_class[cls].append(gap)
            if ha in wall_set and hb in wall_set:
                gaps_conf_by_class[cls].append(gap)

    # ---- assemble thickness_hist ----
    def _class_hists(gapmap):
        counts_by_class = {c: _histogram(gapmap[c], BIN_EDGES) for c in LAYER_CLASSES}
        overall = [0] * (len(BIN_EDGES) - 1)
        for c in LAYER_CLASSES:
            for i, v in enumerate(counts_by_class[c]):
                overall[i] += v
        n_by_class = {c: len(gapmap[c]) for c in LAYER_CLASSES}
        bands = {c: _top_bands(counts_by_class[c], BIN_EDGES) for c in LAYER_CLASSES}
        return counts_by_class, overall, n_by_class, bands

    cbc, overall, n_by_class, bands = _class_hists(gaps_by_class)
    ccbc, coverall, cn_by_class, _ = _class_hists(gaps_conf_by_class)

    thickness_hist = {
        "bin_edges": list(BIN_EDGES),
        "counts": overall,
        "counts_by_class": cbc,
        "candidate_thickness_bands": bands,
        "n_pairs": sum(n_by_class.values()),
        "n_pairs_by_class": n_by_class,
        "params": {
            "angle_tol_deg": ANGLE_TOL_DEG,
            "min_overlap": MIN_OVERLAP,
            "pairing": "within-def LINE pairs (same definition)",
            "gap": "perpendicular spacing of the parallel pair (drawing units)",
            "class": "shared layer class if both lines agree, else 'other'",
            "clamp": "values >= last bin edge are counted in the last bin",
        },
        "wall_confirmed": {
            "definition": "both handles flagged as wall_line_handles by the "
                          "union of all 5 judges",
            "counts": coverall,
            "counts_by_class": ccbc,
            "n_pairs": sum(cn_by_class.values()),
            "n_pairs_by_class": cn_by_class,
        },
    }

    # ---- assemble entity_mix_by_role ----
    entity_mix_by_role = {}
    for role_key in sorted(role_defs):
        entity_mix_by_role[role_key] = {
            "n_defs": role_defs[role_key],
            "total_entities": role_total_entities[role_key],
            "entity_types": dict(sorted(role_entity[role_key].items())),
        }

    # ---- assemble layer_tokens ----
    layer_tokens = {
        "token_freq": dict(sorted(token_freq.items(), key=lambda kv: (-kv[1], kv[0]))),
        "n_distinct_tokens": len(token_freq),
        "n_distinct_layers": len(layer_freq),
        "layer_freq": dict(sorted(layer_freq.items(), key=lambda kv: (-kv[1], kv[0]))),
        "split": "on '$' separators and non-alnum; Hangul counts as alnum; "
                 "weighted by entity count on each layer",
    }

    stats = {
        "stats": STATS_SCHEMA,
        "thickness_hist": thickness_hist,
        "entity_mix_by_role": entity_mix_by_role,
        "layer_tokens": layer_tokens,
        "meta": {
            "reference_judge": REFERENCE_JUDGE,
            "judges_for_wall_handles": list(ALL_JUDGES),
            "n_units": n_units,
            "n_units_with_role": n_units_with_role,
            "n_defs_with_2plus_sampled_lines": n_defs_with_2plus_lines,
            "layer_classes": list(LAYER_CLASSES),
            "note": "LINE coords come from sampled entities (max 30 per def); "
                    "projections carry NO polyline coordinates.",
        },
    }
    return stats


# --------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------

def render_md(stats):
    th = stats["thickness_hist"]
    edges = th["bin_edges"]
    lines = []
    lines.append("# S2-A real-corpus wall statistics (rs.v1)")
    lines.append("")
    lines.append("Fidelity yardstick for the E2 synthetic generator. Extracted "
                 "deterministically from E1 shard projections (LINE coords only) "
                 "and annot_v1 judge annotations.")
    lines.append("")
    m = stats["meta"]
    lines.append(f"- units parsed: **{m['n_units']}** "
                 f"(with reference-judge role: {m['n_units_with_role']})")
    lines.append(f"- defs with >=2 sampled LINEs: **{m['n_defs_with_2plus_sampled_lines']}**")
    lines.append(f"- reference judge (roles): `{m['reference_judge']}`")
    lines.append(f"- wall-handle union judges: {', '.join(m['judges_for_wall_handles'])}")
    lines.append("")

    # thickness
    lines.append("## 1. Parallel LINE-pair spacing (candidate thickness)")
    lines.append("")
    p = th["params"]
    lines.append(f"Pairs: {p['pairing']}; parallel within "
                 f"{p['angle_tol_deg']} deg; overlap ratio >= {p['min_overlap']}. "
                 f"Gap = {p['gap']}. Total pairs: **{th['n_pairs']}** "
                 f"({th['n_pairs_by_class']}).")
    lines.append("")
    lines.append("Histogram (drawing units ~mm), counts per class:")
    lines.append("")
    header = "| bin [lo,hi) | " + " | ".join(LAYER_CLASSES) + " | all |"
    sep = "|" + "---|" * (len(LAYER_CLASSES) + 2)
    lines.append(header)
    lines.append(sep)
    cbc = th["counts_by_class"]
    for i in range(len(edges) - 1):
        row_all = th["counts"][i]
        if row_all == 0:
            continue
        cells = " | ".join(str(cbc[c][i]) for c in LAYER_CLASSES)
        lines.append(f"| {edges[i]}..{edges[i+1]} | {cells} | {row_all} |")
    lines.append("")
    lines.append("Top candidate thickness bands per class (bin, count):")
    for c in LAYER_CLASSES:
        bands = th["candidate_thickness_bands"][c]
        if not bands:
            lines.append(f"- **{c}**: (none)")
            continue
        bstr = ", ".join(f"[{b['range'][0]},{b['range'][1]})={b['count']}" for b in bands)
        lines.append(f"- **{c}**: {bstr}")
    lines.append("")
    wc = th["wall_confirmed"]
    lines.append(f"Judge-wall-confirmed subset ({wc['definition']}): "
                 f"**{wc['n_pairs']}** pairs {wc['n_pairs_by_class']}.")
    lines.append("")

    # entity mix
    lines.append("## 2. Entity-type mix per def role (reference judge)")
    lines.append("")
    emr = stats["entity_mix_by_role"]
    all_types = sorted({t for r in emr.values() for t in r["entity_types"]})
    lines.append("| role | n_defs | total_entities | " + " | ".join(all_types) + " |")
    lines.append("|" + "---|" * (3 + len(all_types)))
    for role in sorted(emr, key=lambda r: (-emr[r]["n_defs"], r)):
        r = emr[role]
        cells = " | ".join(str(r["entity_types"].get(t, 0)) for t in all_types)
        lines.append(f"| {role} | {r['n_defs']} | {r['total_entities']} | {cells} |")
    lines.append("")

    # layer tokens
    lines.append("## 3. Layer-token frequency ($ + non-alnum split)")
    lines.append("")
    lt = stats["layer_tokens"]
    lines.append(f"{lt['n_distinct_tokens']} distinct tokens across "
                 f"{lt['n_distinct_layers']} distinct layers "
                 f"(weighted by entity count). Top 30:")
    lines.append("")
    lines.append("| token | weighted count |")
    lines.append("|---|---|")
    for i, (tok, cnt) in enumerate(lt["token_freq"].items()):
        if i >= 30:
            break
        lines.append(f"| `{tok}` | {cnt} |")
    lines.append("")
    lines.append("## LIMITS")
    lines.append("")
    lines.append("- Spacing is over **sampled** LINEs (<=30 per def); defs with "
                 "more entities have partial LINE coverage.")
    lines.append("- WALL class = LINE on a wall-family layer (W/W<n>/WALL); a "
                 "WALL pair's gap is NOT necessarily a wall thickness (wall "
                 "layers also carry room-boundary spans).")
    lines.append("- Polylines (LWPOLYLINE) carry no coordinates in projections "
                 "and contribute no spacing pairs.")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

def _write_fixture(root):
    """Build a tiny self-contained corpus under root (OS temp dir)."""
    shards = os.path.join(root, "shards")
    jroot = os.path.join(root, "judges", REFERENCE_JUDGE)
    os.makedirs(shards)
    os.makedirs(jroot)

    def proj(name, ec, dxf, lay, ents):
        p = [
            "DWG block definition annotation task",
            f"Definition name: {name}",
            f"entity_count: {ec}",
            "dxf_name histogram: " + ", ".join(f"{k}={v}" for k, v in dxf),
            "layer histogram: " + ", ".join(f"{k}={v}" for k, v in lay),
            "bbox from LINE start/end: [0, 0, 0, 100, 100, 0]",
            "sampled entities (max 30):",
        ]
        p.extend(ents)
        p.append("")
        p.append("Instructions / done.")
        return "\n".join(p)

    # T1: two vertical parallel WALL lines 250 apart, fully overlapping.
    t1_ents = [
        "- LINE layer=X-P(a)$0$W1 handle=A1 (0,0)->(0,1000)",
        "- LINE layer=X-P(a)$0$W1 handle=A2 (250,0)->(250,1000)",
    ]
    # T2: two horizontal DOOR lines 2 apart (double-line leaf).
    t2_ents = [
        "- LINE layer=X-P(a)$0$DOOR handle=B1 (0,0)->(500,0)",
        "- LINE layer=X-P(a)$0$DOOR handle=B2 (0,2)->(500,2)",
        "- ARC layer=X-P(a)$0$DOOR handle=B3",
    ]
    recs = [
        {"kind": "def_annotation", "unit_id": "u-t1",
         "prompt": proj("*T1", 2, [("LINE", 2)], [("X-P(a)$0$W1", 2)], t1_ents)},
        {"kind": "def_annotation", "unit_id": "u-t2",
         "prompt": proj("*T2", 3, [("LINE", 2), ("ARC", 1)],
                        [("X-P(a)$0$DOOR", 3)], t2_ents)},
    ]
    with open(os.path.join(shards, "shard_01.jsonl"), "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Judge file: T1 role plan + BOTH handles wall-flagged (string form);
    # T2 role symbol + object-form handle (tests both parse paths).
    judge = [
        {"unit_id": "u-t1", "def": "*T1", "role": "plan", "wall_likelihood": 0.9,
         "wall_line_handles": ["A1", "A2"], "notes": "", "rationale": {}},
        {"unit_id": "u-t2", "def": "*T2", "role": "symbol", "wall_likelihood": 0.1,
         "wall_line_handles": [{"handle": "B1", "reason": "leaf"}],
         "notes": "", "rationale": {}},
    ]
    with open(os.path.join(jroot, "shard_01.json"), "w", encoding="utf-8") as fh:
        json.dump(judge, fh, ensure_ascii=False)

    # Populate the other judge dirs (empty shards) so load_judges is exercised.
    for j in ALL_JUDGES:
        if j == REFERENCE_JUDGE:
            continue
        d = os.path.join(root, "judges", j)
        os.makedirs(d)
        with open(os.path.join(d, "shard_01.json"), "w", encoding="utf-8") as fh:
            json.dump([], fh)
    return shards, os.path.join(root, "judges")


def selftest():
    failures = []

    def check(cond, msg):
        status = "PASS" if cond else "FAIL"
        print(f"[{status}] {msg}")
        if not cond:
            failures.append(msg)

    # unit tests: tokenize / classify
    toks = tokenize_layer("X-평면도(기본형)$0$W1")
    check(toks == ["X", "평면도", "기본형", "0", "W1"],
          f"tokenize splits $ and non-alnum, keeps Hangul: {toks}")
    check(classify_layer("DIM") == "DIM", "classify DIM -> DIM")
    check(classify_layer("DEFPOINTS") == "DIM", "classify DEFPOINTS -> DIM")
    check(classify_layer("X-P(a)$0$DOOR") == "DOOR", "classify *$DOOR -> DOOR")
    check(classify_layer("X-P(a)$0$W1") == "WALL", "classify *$W1 -> WALL")
    check(classify_layer("X-P(a)$0$W2") == "WALL", "classify *$W2 -> WALL")
    check(classify_layer("X-P(a)$0$FUR") == "other", "classify *$FUR -> other")

    # handle extraction: both forms
    check(_extract_handle("A1") == "A1", "extract str handle")
    check(_extract_handle({"handle": "B1", "reason": "x"}) == "B1",
          "extract obj handle")
    check(_extract_handle({"reason": "x"}) is None, "extract obj no-handle -> None")

    # histogram + clamp
    h = _histogram([0.5, 250, 260, 1e9], BIN_EDGES)
    check(sum(h) == 4 and h[-1] == 1,
          f"histogram clamps overflow into last bin: {h}")
    idx250 = bisect.bisect_right(BIN_EDGES, 250) - 1
    check(h[idx250] == 2, f"250 and 260 land in [250,300) bin idx={idx250}")

    # projection parse: unknown shape -> kind other, no crash
    proj = parse_projection(
        "Definition name: *X\nentity_count: 1\n"
        "dxf_name histogram: LINE=1\nlayer histogram: DIM=1\n"
        "sampled entities (max 30):\n- WELDOMATIC gibberish no match\n"
    )
    check(proj is not None and proj["sampled"][0]["kind"] == "other",
          "unknown entity line -> kind='other', no crash")

    # end-to-end on fixture
    tmp = tempfile.mkdtemp(prefix="s2a_selftest_")
    shards, judges = _write_fixture(tmp)
    stats = build_stats(shards, judges)

    check(stats["stats"] == STATS_SCHEMA, "schema tag rs.v1")
    th = stats["thickness_hist"]
    check(len(th["bin_edges"]) == len(th["counts"]) + 1,
          "bin_edges length == counts length + 1")
    wall_counts = th["counts_by_class"]["WALL"]
    check(wall_counts[idx250] >= 1,
          f"WALL 250mm pair lands in [250,300): {wall_counts[idx250]}")
    door_bin = bisect.bisect_right(BIN_EDGES, 2) - 1
    check(th["counts_by_class"]["DOOR"][door_bin] >= 1,
          f"DOOR 2mm pair lands in [2,5): {th['counts_by_class']['DOOR'][door_bin]}")
    check(th["wall_confirmed"]["n_pairs"] == 1,
          f"wall-confirmed = T1 pair only (both handles flagged): "
          f"{th['wall_confirmed']['n_pairs']}")

    emr = stats["entity_mix_by_role"]
    check(emr.get("plan", {}).get("entity_types", {}).get("LINE") == 2,
          "entity_mix_by_role[plan][LINE] == 2")
    check(emr.get("symbol", {}).get("entity_types", {}).get("ARC") == 1,
          "entity_mix_by_role[symbol][ARC] == 1")

    lt = stats["layer_tokens"]["token_freq"]
    check(lt.get("W1", 0) >= 1 and lt.get("DOOR", 0) >= 1,
          f"layer_tokens has W1 and DOOR: W1={lt.get('W1')} DOOR={lt.get('DOOR')}")

    # md renders without error
    md = render_md(stats)
    check(md.startswith("# S2-A"), "markdown renders")

    print("")
    if failures:
        print(f"SELFTEST RESULT: FAIL ({len(failures)} failing checks)")
        return 1
    print("SELFTEST RESULT: PASS (all checks green)")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", default=str(repo_root / "bench" / "e1_shards"))
    parser.add_argument("--judges",
                        default=str(repo_root / "reports" / "e1" / "annot_v1" / "raw"))
    parser.add_argument("--out-json",
                        default=str(repo_root / "reports" / "e2" / "s2" / "real_stats.json"))
    parser.add_argument("--out-md",
                        default=str(repo_root / "reports" / "e2" / "s2" / "real_stats.md"))
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    stats = build_stats(args.shards, args.judges)
    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    with open(args.out_md, "w", encoding="utf-8") as fh:
        fh.write(render_md(stats))

    th = stats["thickness_hist"]
    print(f"wrote {args.out_json}")
    print(f"wrote {args.out_md}")
    print(f"units={stats['meta']['n_units']} "
          f"pairs={th['n_pairs']} {th['n_pairs_by_class']} "
          f"roles={len(stats['entity_mix_by_role'])} "
          f"tokens={stats['layer_tokens']['n_distinct_tokens']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
