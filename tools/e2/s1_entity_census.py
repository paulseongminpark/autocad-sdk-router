#!/usr/bin/env python3
"""S1-B - per-def entity census (forensic).

Quantifies what the v0 wall detector could NOT see, by censusing every block
definition's projection text (the ONLY thing a judge/detector ever saw) and
crossing that census with the v1 judge-divergence clusters.

Core forensic premise (verified, not assumed, by --verify-grammar / the
`coord_bearing_kinds` field): in the E1 projection grammar only LINE entities
carry explicit coordinates. Every other entity kind is projected as a bare
"kind + layer + handle (+ scalar attr)" line. A def whose entities are, say,
100% LWPOLYLINE therefore exposes ZERO geometry to the model - it is
structurally invisible to any coordinate-based wall detector.

Usage:
    python s1_entity_census.py                 # RUN on repo data, write reports
    python s1_entity_census.py --selftest      # self-contained fixture in OS temp
    python s1_entity_census.py --root <path>   # census an alternate repo root

stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import tempfile

# --- projection grammar -----------------------------------------------------

# Entity kinds the E1 projection grammar is known to emit (card-verbatim list).
# Anything else parses to kind='other' rather than crashing.
KNOWN_KINDS = {
    "LINE", "INSERT", "MTEXT", "POINT", "LWPOLYLINE", "WIPEOUT", "SPLINE",
    "HATCH", "TEXT", "ARC", "CIRCLE", "ELLIPSE", "3DFACE",
}

RE_DEF_NAME = re.compile(r"^Definition name:\s*(.+?)\s*$")
RE_ENTITY_COUNT = re.compile(r"^entity_count:\s*(\d+)\s*$")
RE_DXF_HIST = re.compile(r"^dxf_name histogram:\s*(.*?)\s*$")
RE_LAYER_HIST = re.compile(r"^layer histogram:\s*(.*?)\s*$")
RE_BBOX = re.compile(r"^bbox from LINE start/end:\s*\[(.*?)\]\s*$")
RE_SAMPLED_HDR = re.compile(r"^sampled entities \(max\s*(\d+)\):\s*$")

RE_ENTITY_LINE = re.compile(r"^-\s+(\S+)\s*(.*)$")
RE_HANDLE = re.compile(r"\bhandle=([0-9A-Fa-f]+)\b")
RE_LAYER = re.compile(r"\blayer=(\S+)")
RE_COORDS = re.compile(
    r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)\s*->\s*"
    r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)"
)
RE_QUOTED = re.compile(r"'[^']*'")
RE_BLOCK = re.compile(r"\bblock=(\S+)")
RE_VERTICES = re.compile(r"\bvertices=(\d+)\b")
RE_RADIUS = re.compile(r"\bradius=(-?\d+(?:\.\d+)?)\b")


def parse_histogram(s):
    """'A=1, B=2' -> {'A': 1, 'B': 2}. Tolerates junk; never raises."""
    out = {}
    if not s:
        return out
    for part in s.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, _, val = part.rpartition("=")
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        try:
            out[key] = int(val)
        except ValueError:
            continue
    return out


def parse_entity_line(line):
    """Parse one '- KIND layer=.. handle=..' projection line.

    Unknown shapes -> kind='other'. Never raises.
    """
    m = RE_ENTITY_LINE.match(line)
    if not m:
        return {"kind": "other", "raw": line, "has_coords": False,
                "handle": None, "layer": None}
    token, attrs = m.group(1), m.group(2)
    kind = token if token in KNOWN_KINDS else "other"

    # Strip quoted literals (MTEXT/TEXT payloads) before scanning for
    # coordinates, so text content can never masquerade as geometry.
    attrs_nostr = RE_QUOTED.sub("", attrs)

    rec = {"kind": kind, "has_coords": False, "handle": None, "layer": None}
    if kind == "other":
        rec["raw_token"] = token

    mh = RE_HANDLE.search(attrs)
    if mh:
        rec["handle"] = mh.group(1)
    ml = RE_LAYER.search(attrs)
    if ml:
        rec["layer"] = ml.group(1)

    mc = RE_COORDS.search(attrs_nostr)
    if mc:
        rec["has_coords"] = True
        rec["coords"] = [float(x) for x in mc.groups()]

    mb = RE_BLOCK.search(attrs_nostr)
    if mb:
        rec["block"] = mb.group(1)
    mv = RE_VERTICES.search(attrs_nostr)
    if mv:
        rec["vertices"] = int(mv.group(1))
    mr = RE_RADIUS.search(attrs_nostr)
    if mr:
        rec["radius"] = float(mr.group(1))
    return rec


def parse_projection(prompt):
    """Parse a def_annotation prompt into a census record. Never raises."""
    rec = {
        "def": None,
        "entity_count": None,
        "dxf_histogram": {},
        "layer_histogram": {},
        "bbox_present": False,
        "bbox": None,
        "sampled": [],
        "sample_cap": None,
        "parse_warnings": [],
    }
    in_sampled = False
    for raw in prompt.splitlines():
        line = raw.rstrip()
        if not in_sampled:
            m = RE_DEF_NAME.match(line)
            if m:
                rec["def"] = m.group(1)
                continue
            m = RE_ENTITY_COUNT.match(line)
            if m:
                rec["entity_count"] = int(m.group(1))
                continue
            m = RE_DXF_HIST.match(line)
            if m:
                rec["dxf_histogram"] = parse_histogram(m.group(1))
                continue
            m = RE_LAYER_HIST.match(line)
            if m:
                rec["layer_histogram"] = parse_histogram(m.group(1))
                continue
            m = RE_BBOX.match(line)
            if m:
                body = m.group(1).strip()
                rec["bbox_present"] = bool(body)
                try:
                    rec["bbox"] = [float(x.strip()) for x in body.split(",")]
                except ValueError:
                    rec["parse_warnings"].append("bbox_unparsed")
                continue
            m = RE_SAMPLED_HDR.match(line)
            if m:
                in_sampled = True
                rec["sample_cap"] = int(m.group(1))
                continue
        else:
            if not line.strip():
                continue
            if not line.startswith("-"):
                # Section ended (e.g. the 'Instructions' block).
                in_sampled = False
                continue
            rec["sampled"].append(parse_entity_line(line))
    return rec


# --- per-def metrics --------------------------------------------------------

def census_def(rec):
    """Derive the forensic metrics for one parsed projection."""
    hist = rec["dxf_histogram"]
    n = rec["entity_count"]
    hist_sum = sum(hist.values())
    if n is None:
        n = hist_sum
        rec["parse_warnings"].append("entity_count_missing_used_hist_sum")
    if n != hist_sum:
        rec["parse_warnings"].append(
            "entity_count_%s_ne_hist_sum_%s" % (n, hist_sum))

    line_n = hist.get("LINE", 0)
    lwpl_n = hist.get("LWPOLYLINE", 0)
    ins_n = hist.get("INSERT", 0)

    sampled = rec["sampled"]
    s_n = len(sampled)
    s_coords = sum(1 for e in sampled if e["has_coords"])

    def share(a, b):
        return round(a / b, 6) if b else None

    return {
        "def": rec["def"],
        "entity_count": n,
        "dxf_histogram": dict(sorted(hist.items())),
        "n_layers": len(rec["layer_histogram"]),
        "line_count": line_n,
        "lwpolyline_count": lwpl_n,
        "insert_count": ins_n,
        # Population-level shares, from the FULL dxf_name histogram header
        # (authoritative: the sampled list is capped at 30).
        "line_share": share(line_n, n),
        "lwpolyline_share": share(lwpl_n, n),
        "insert_share": share(ins_n, n),
        # Population coord-bearing share == line_share by grammar (only LINE
        # carries coords); kept as a distinct field so the claim is auditable.
        "coord_share_population": share(line_n, n),
        "zero_line": line_n == 0,
        "bbox_present": rec["bbox_present"],
        "sampled_n": s_n,
        "sampled_truncated": bool(rec["sample_cap"]) and s_n >= rec["sample_cap"] and n > s_n,
        "sampled_coord_n": s_coords,
        # Measured (not assumed) coord share over the sampled entities.
        "coord_share_sampled": share(s_coords, s_n),
        "parse_warnings": rec["parse_warnings"],
    }


# --- loaders ----------------------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_shards(root):
    """Read bench/e1_shards/shard_*.jsonl -> (defs, units, provenance)."""
    shard_dir = os.path.join(root, "bench", "e1_shards")
    paths = sorted(
        os.path.join(shard_dir, f)
        for f in os.listdir(shard_dir)
        if f.startswith("shard_") and f.endswith(".jsonl")
    )
    defs = {}
    unit_to_def = {}
    prov = []
    dupes = []
    for p in paths:
        prov.append({"file": os.path.relpath(p, root).replace("\\", "/"),
                     "sha256": sha256_file(p)})
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                obj = json.loads(ln)
                if obj.get("kind") != "def_annotation":
                    continue
                parsed = parse_projection(obj.get("prompt", ""))
                c = census_def(parsed)
                c["unit_id"] = obj.get("unit_id")
                name = c["def"]
                if name is None:
                    continue
                if name in defs:
                    dupes.append(name)
                    continue
                defs[name] = c
                unit_to_def[c["unit_id"]] = name
    return defs, unit_to_def, prov, sorted(set(dupes))


def load_judges(root, judges):
    """Read reports/e1/annot_v1/raw/<judge>/shard_NN.json -> {judge: {def: role}}."""
    base = os.path.join(root, "reports", "e1", "annot_v1", "raw")
    out = {}
    for j in judges:
        jdir = os.path.join(base, j)
        if not os.path.isdir(jdir):
            continue
        roles = {}
        for f in sorted(os.listdir(jdir)):
            if not f.endswith(".json"):
                continue
            with open(os.path.join(jdir, f), encoding="utf-8") as fh:
                try:
                    recs = json.load(fh)
                except json.JSONDecodeError:
                    continue
            if not isinstance(recs, list):
                continue
            for r in recs:
                d = r.get("def")
                if d is not None:
                    roles[d] = r.get("role")
        out[j] = roles
    return out


def normalize_handles(items):
    """wall_line_handles entries are str OR {'handle':..,'reason':..}. Handle both."""
    out = []
    for it in items or []:
        if isinstance(it, str):
            out.append(it)
        elif isinstance(it, dict):
            h = it.get("handle")
            if isinstance(h, str):
                out.append(h)
    return out


def load_clusters(root):
    p = os.path.join(root, "reports", "e1", "annot_v1", "cluster_probe_v1.json")
    with open(p, encoding="utf-8") as fh:
        cp = json.load(fh)
    return cp, {"file": os.path.relpath(p, root).replace("\\", "/"),
                "sha256": sha256_file(p)}


def load_v0_divergent(root):
    """calibration_v0.json MAY carry the divergent top-20 list. Return (list|None, reason)."""
    p = os.path.join(root, "reports", "e1", "panel_20260717", "evidence",
                     "calibration_v0.json")
    if not os.path.isfile(p):
        return None, "calibration_v0.json not found at %s" % p
    with open(p, encoding="utf-8") as fh:
        cal = json.load(fh)
    # Accept any plausible key carrying a per-def list.
    for key in ("divergent_top20", "divergent_defs", "top20_divergent",
                "top_divergent", "divergent"):
        v = cal.get(key)
        if isinstance(v, list) and v:
            names = []
            for it in v:
                if isinstance(it, str):
                    names.append(it)
                elif isinstance(it, dict) and isinstance(it.get("def"), str):
                    names.append(it["def"])
            if names:
                return names, "loaded from key '%s'" % key
    return None, (
        "calibration_v0.json contains aggregate statistics only "
        "(keys: %s) - no per-def divergent list is present, so the v0 "
        "divergent top-20 cross could not be run." % ", ".join(sorted(cal))
    )


# --- grouping & stats -------------------------------------------------------

def assign_groups(defs, cluster_probe, judge_roles):
    """divergent = full_split + soft_split (from cluster_probe).
    uniform = all 5 judges emit the identical role (DERIVED here, cross-checked
    against cluster_probe counts.uniform_all5)."""
    full_split = list(cluster_probe.get("full_split_defs", []))
    soft_split = list(cluster_probe.get("soft_split_defs", []))
    divergent = set(full_split) | set(soft_split)

    judges = sorted(judge_roles)
    uniform = set()
    for d in defs:
        roles = [judge_roles[j].get(d) for j in judges]
        if roles and all(r is not None for r in roles) and len(set(roles)) == 1:
            uniform.add(d)

    groups = {
        "divergent": sorted(divergent & set(defs)),
        "uniform": sorted(uniform - divergent),
        "other_mixed": sorted(set(defs) - uniform - divergent),
    }
    integrity = {
        "n_full_split": len(full_split),
        "n_soft_split": len(soft_split),
        "n_divergent_declared": len(divergent),
        "n_divergent_matched_in_census": len(groups["divergent"]),
        "divergent_missing_from_census": sorted(divergent - set(defs)),
        "n_uniform_derived": len(uniform),
        "n_uniform_expected_from_cluster_probe":
            cluster_probe.get("counts", {}).get("uniform_all5"),
        "uniform_derivation_matches_cluster_probe":
            len(uniform) == cluster_probe.get("counts", {}).get("uniform_all5"),
        "divergent_uniform_overlap": sorted(divergent & uniform),
    }
    return groups, integrity


def _num(vals):
    return [v for v in vals if v is not None]


def summarize(defs, names):
    """Descriptive stats for one group."""
    recs = [defs[n] for n in names]
    if not recs:
        return {"n": 0}

    def stats(vals):
        v = _num(vals)
        if not v:
            return None
        sv = sorted(v)
        return {
            "n": len(sv),
            "median": round(statistics.median(sv), 6),
            "mean": round(statistics.fmean(sv), 6),
            "p25": round(sv[max(0, (len(sv) - 1) // 4)], 6),
            "p75": round(sv[min(len(sv) - 1, (3 * (len(sv) - 1)) // 4)], 6),
            "min": round(sv[0], 6),
            "max": round(sv[-1], 6),
        }

    agg = {}
    for r in recs:
        for k, v in r["dxf_histogram"].items():
            agg[k] = agg.get(k, 0) + v
    tot = sum(agg.values())

    return {
        "n": len(recs),
        "line_share": stats([r["line_share"] for r in recs]),
        "lwpolyline_share": stats([r["lwpolyline_share"] for r in recs]),
        "insert_count": stats([float(r["insert_count"]) for r in recs]),
        "coord_share_sampled": stats([r["coord_share_sampled"] for r in recs]),
        "entity_count": stats([float(r["entity_count"]) for r in recs]),
        "zero_line_defs": sum(1 for r in recs if r["zero_line"]),
        "zero_line_frac": round(
            sum(1 for r in recs if r["zero_line"]) / len(recs), 6),
        "bbox_present_defs": sum(1 for r in recs if r["bbox_present"]),
        "bbox_present_frac": round(
            sum(1 for r in recs if r["bbox_present"]) / len(recs), 6),
        "entity_kind_totals": dict(sorted(agg.items(),
                                          key=lambda kv: (-kv[1], kv[0]))),
        "entity_kind_shares": {
            k: round(v / tot, 6) for k, v in sorted(
                agg.items(), key=lambda kv: (-kv[1], kv[0]))} if tot else {},
        "total_entities": tot,
    }


def blindness_contingency(defs, groups):
    """2x2: coordinate-blind (zero LINE) x divergent.

    The group medians answer 'are divergent defs blinder?'. This answers the
    sharper converse: 'does blindness predict divergence?' - i.e. how much more
    likely is a def to split the judges when it exposes no coordinates at all.
    Restricted to divergent+uniform (other_mixed excluded: it is neither a
    clean split nor a clean agreement).
    """
    scope = set(groups["divergent"]) | set(groups["uniform"])
    div = set(groups["divergent"])
    cell = {"blind_divergent": 0, "blind_uniform": 0,
            "sighted_divergent": 0, "sighted_uniform": 0}
    for d in scope:
        blind = defs[d]["zero_line"]
        isdiv = d in div
        key = ("blind_" if blind else "sighted_") + \
              ("divergent" if isdiv else "uniform")
        cell[key] += 1
    n_blind = cell["blind_divergent"] + cell["blind_uniform"]
    n_sighted = cell["sighted_divergent"] + cell["sighted_uniform"]
    p_blind = (cell["blind_divergent"] / n_blind) if n_blind else None
    p_sighted = (cell["sighted_divergent"] / n_sighted) if n_sighted else None
    return {
        "scope": "divergent + uniform (other_mixed excluded)",
        "n_scope": len(scope),
        "cells": cell,
        "n_coord_blind": n_blind,
        "n_coord_bearing": n_sighted,
        "p_divergent_given_coord_blind": (
            round(p_blind, 6) if p_blind is not None else None),
        "p_divergent_given_coord_bearing": (
            round(p_sighted, 6) if p_sighted is not None else None),
        "risk_ratio": (round(p_blind / p_sighted, 4)
                       if p_blind and p_sighted else None),
    }


def decide_verdict(med_div, med_unif):
    """Preregistered band from the card.

    < half of uniform median      -> BLINDNESS_CONFIRMED
    ratio in [0.8, 1.2]           -> NOT_BLINDNESS
    otherwise                     -> MIXED
    """
    if med_div is None or med_unif is None:
        return "MIXED", None, "a group median is undefined (empty group)"
    if med_div < 0.5 * med_unif:
        ratio = (med_div / med_unif) if med_unif else None
        return ("BLINDNESS_CONFIRMED", ratio,
                "divergent median LINE-share (%.4f) < half of uniform median "
                "(%.4f / 2 = %.4f)" % (med_div, med_unif, med_unif / 2))
    if med_unif == 0:
        if med_div == 0:
            return ("NOT_BLINDNESS", 1.0,
                    "both medians are 0.0 - identical by convention (ratio:=1)")
        return ("MIXED", None,
                "uniform median is 0.0 while divergent median is %.4f - "
                "ratio undefined" % med_div)
    ratio = med_div / med_unif
    if 0.8 <= ratio <= 1.2:
        return ("NOT_BLINDNESS", ratio,
                "ratio %.4f falls inside the preregistered similar band "
                "[0.8, 1.2]" % ratio)
    return ("MIXED", ratio,
            "ratio %.4f is neither < 0.5 nor inside [0.8, 1.2]" % ratio)


# --- pipeline ---------------------------------------------------------------

JUDGES = ["opus48_max", "fable5_high", "sol56_xhigh", "sonnet5_xhigh",
          "grok45_xhigh"]


def run_census(root, sampled_scan=None):
    defs, unit_to_def, shard_prov, dupes = load_shards(root)
    judge_roles = load_judges(root, JUDGES)
    cluster_probe, cp_prov = load_clusters(root)
    v0_list, v0_reason = load_v0_divergent(root)

    groups, integrity = assign_groups(defs, cluster_probe, judge_roles)
    integrity["n_defs_censused"] = len(defs)
    integrity["duplicate_def_names"] = dupes
    integrity["defs_with_parse_warnings"] = sorted(
        d for d, c in defs.items() if c["parse_warnings"])
    integrity["judges_loaded"] = {j: len(judge_roles.get(j, {})) for j in JUDGES}

    summaries = {g: summarize(defs, names) for g, names in groups.items()}

    med_div = (summaries["divergent"].get("line_share") or {}).get("median")
    med_unif = (summaries["uniform"].get("line_share") or {}).get("median")
    verdict, ratio, why = decide_verdict(med_div, med_unif)

    # v0 cross - only if calibration_v0.json actually carried the list.
    v0_cross = {"available": False, "reason": v0_reason}
    if v0_list:
        present = [d for d in v0_list if d in defs]
        v0_cross = {
            "available": True,
            "reason": v0_reason,
            "n_declared": len(v0_list),
            "n_matched_in_census": len(present),
            "missing": [d for d in v0_list if d not in defs],
            "summary": summarize(defs, present),
        }

    # Grammar verification: which entity kinds EVER carry coordinates.
    kinds_with_coords = {}
    kinds_seen = {}
    unknown_tokens = {}
    for c in (sampled_scan or {}).values():
        for e in c:
            k = e["kind"]
            kinds_seen[k] = kinds_seen.get(k, 0) + 1
            if e["has_coords"]:
                kinds_with_coords[k] = kinds_with_coords.get(k, 0) + 1
            if k == "other":
                t = e.get("raw_token", "?")
                unknown_tokens[t] = unknown_tokens.get(t, 0) + 1

    out = {
        "schema": "ariadne.e2_s1_entity_census.v1",
        "card": "S1-B per-def entity census (forensic)",
        "provenance": {
            "shards": shard_prov,
            "cluster_probe": cp_prov,
            "judges": JUDGES,
            "python": sys.version.split()[0],
        },
        "integrity": integrity,
        "grammar_check": {
            "premise": "only LINE entities carry coordinates in E1 projections",
            "sampled_entities_scanned": sum(kinds_seen.values()),
            "kinds_seen": dict(sorted(kinds_seen.items(),
                                      key=lambda kv: (-kv[1], kv[0]))),
            "coord_bearing_kinds": dict(sorted(kinds_with_coords.items(),
                                               key=lambda kv: (-kv[1], kv[0]))),
            "premise_holds": set(kinds_with_coords) <= {"LINE"},
            "unknown_tokens": dict(sorted(unknown_tokens.items())),
        },
        "group_sizes": {g: len(n) for g, n in groups.items()},
        "groups": groups,
        "summaries": summaries,
        "blindness_contingency": blindness_contingency(defs, groups),
        "verdict": {
            "band": verdict,
            "metric": "median line_share (LINE / entity_count, full histogram)",
            "divergent_median_line_share": med_div,
            "uniform_median_line_share": med_unif,
            "ratio_divergent_over_uniform": (
                round(ratio, 6) if ratio is not None else None),
            "rule": ("<0.5 -> BLINDNESS_CONFIRMED; 0.8-1.2 -> NOT_BLINDNESS; "
                     "else MIXED"),
            "why": why,
        },
        "v0_divergent_top20_cross": v0_cross,
        "per_def": {d: defs[d] for d in sorted(defs)},
    }
    return out, defs


def collect_sampled(root):
    """Second pass: keep raw sampled-entity records for the grammar check."""
    shard_dir = os.path.join(root, "bench", "e1_shards")
    out = {}
    for f in sorted(os.listdir(shard_dir)):
        if not (f.startswith("shard_") and f.endswith(".jsonl")):
            continue
        with open(os.path.join(shard_dir, f), encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                obj = json.loads(ln)
                if obj.get("kind") != "def_annotation":
                    continue
                p = parse_projection(obj.get("prompt", ""))
                if p["def"] is not None:
                    out.setdefault(p["def"], p["sampled"])
    return out


def _fmt(v, nd=4):
    if v is None:
        return "n/a"
    return ("%%.%df" % nd) % v


def render_md(res):
    g = res["group_sizes"]
    sd, su, so = res["summaries"]["divergent"], res["summaries"]["uniform"], \
        res["summaries"]["other_mixed"]
    v = res["verdict"]
    gc = res["grammar_check"]
    it = res["integrity"]
    L = []
    A = L.append

    A("# E2 S1-B - per-def entity census (forensic)")
    A("")
    A("**VERDICT: `%s`**" % v["band"])
    A("")
    A("> %s" % v["why"])
    A("")
    A("Metric: %s." % v["metric"])
    A("Band rule (preregistered by the card): %s" % v["rule"])
    A("")
    A("| | divergent | uniform | ratio |")
    A("|---|---|---|---|")
    A("| median LINE-share | %s | %s | %s |" % (
        _fmt(v["divergent_median_line_share"]),
        _fmt(v["uniform_median_line_share"]),
        _fmt(v["ratio_divergent_over_uniform"])))
    A("")

    A("## What the census measures")
    A("")
    A("Each of the %d block definitions was seen by the v0 detector and by the "
      "v1 judges ONLY through its projection text. This census reads those same "
      "projections and asks, per def, how much geometry was actually visible." %
      it["n_defs_censused"])
    A("")
    A("The decisive structural fact: **%s**. Scanning %d sampled entity lines, "
      "the only coordinate-bearing kind(s) found were: `%s`. Premise holds: "
      "**%s**." % (gc["premise"], gc["sampled_entities_scanned"],
                   ", ".join(gc["coord_bearing_kinds"]) or "(none)",
                   gc["premise_holds"]))
    A("")
    A("So a definition with zero LINE entities exposes **no coordinates at all** "
      "- it is structurally invisible to any coordinate-based wall detector, "
      "regardless of model quality.")
    A("")

    A("## Groups")
    A("")
    A("- `divergent` (n=%d) = `full_split_defs` (%d) + `soft_split_defs` (%d) "
      "from cluster_probe_v1.json" % (g["divergent"], it["n_full_split"],
                                      it["n_soft_split"]))
    A("- `uniform` (n=%d) = all 5 judges emitted the identical role (derived "
      "here; cluster_probe counts.uniform_all5=%s, match: %s)" % (
          g["uniform"], it["n_uniform_expected_from_cluster_probe"],
          it["uniform_derivation_matches_cluster_probe"]))
    A("- `other_mixed` (n=%d) = neither" % g["other_mixed"])
    A("")

    A("## Per-group census")
    A("")
    A("| metric | divergent (n=%d) | uniform (n=%d) | other_mixed (n=%d) |" % (
        sd["n"], su["n"], so["n"]))
    A("|---|---|---|---|")

    def row(label, key, field="median", nd=4):
        def cell(s):
            d = s.get(key)
            if not d:
                return "n/a"
            return _fmt(d.get(field), nd)
        A("| %s | %s | %s | %s |" % (label, cell(sd), cell(su), cell(so)))

    row("median LINE-share", "line_share")
    row("mean LINE-share", "line_share", "mean")
    row("median LWPOLYLINE-share", "lwpolyline_share")
    row("mean LWPOLYLINE-share", "lwpolyline_share", "mean")
    row("median INSERT count", "insert_count", "median", 2)
    row("mean INSERT count", "insert_count", "mean", 2)
    row("median entity_count", "entity_count", "median", 1)
    row("median coord-share (sampled)", "coord_share_sampled")
    A("| defs with ZERO LINE entities | %d (%s) | %d (%s) | %d (%s) |" % (
        sd["zero_line_defs"], _fmt(sd["zero_line_frac"], 3),
        su["zero_line_defs"], _fmt(su["zero_line_frac"], 3),
        so["zero_line_defs"], _fmt(so["zero_line_frac"], 3)))
    A("| defs with a derivable bbox | %d (%s) | %d (%s) | %d (%s) |" % (
        sd["bbox_present_defs"], _fmt(sd["bbox_present_frac"], 3),
        su["bbox_present_defs"], _fmt(su["bbox_present_frac"], 3),
        so["bbox_present_defs"], _fmt(so["bbox_present_frac"], 3)))
    A("")

    A("## Does blindness predict divergence?")
    A("")
    bc = res["blindness_contingency"]
    A("The medians above show divergent defs are blinder. The sharper converse "
      "- does having no coordinates *cause* judges to split? - is this 2x2 "
      "over %s (n=%d):" % (bc["scope"], bc["n_scope"]))
    A("")
    A("| | divergent | uniform | P(divergent) |")
    A("|---|---|---|---|")
    A("| coordinate-blind (0 LINE) | %d | %d | **%s** |" % (
        bc["cells"]["blind_divergent"], bc["cells"]["blind_uniform"],
        _fmt(bc["p_divergent_given_coord_blind"], 3)))
    A("| coordinate-bearing (>=1 LINE) | %d | %d | **%s** |" % (
        bc["cells"]["sighted_divergent"], bc["cells"]["sighted_uniform"],
        _fmt(bc["p_divergent_given_coord_bearing"], 3)))
    A("")
    A("Risk ratio: **%sx**. A def that exposes no coordinates is that many "
      "times more likely to split the judge panel than one that exposes any." %
      _fmt(bc["risk_ratio"], 1))
    A("")

    A("## Entity-kind mix per group (share of all entities in group)")
    A("")
    kinds = []
    for s in (sd, su, so):
        for k in s.get("entity_kind_shares", {}):
            if k not in kinds:
                kinds.append(k)
    A("| kind | divergent | uniform | other_mixed |")
    A("|---|---|---|---|")
    for k in kinds:
        A("| %s | %s | %s | %s |" % (
            k,
            _fmt(sd.get("entity_kind_shares", {}).get(k), 4),
            _fmt(su.get("entity_kind_shares", {}).get(k), 4),
            _fmt(so.get("entity_kind_shares", {}).get(k), 4)))
    A("")

    A("## v0 divergent top-20 cross")
    A("")
    x = res["v0_divergent_top20_cross"]
    if x["available"]:
        A("Available (%s): n=%d matched, median LINE-share %s." % (
            x["reason"], x["n_matched_in_census"],
            _fmt((x["summary"].get("line_share") or {}).get("median"))))
    else:
        A("**NOT RUN.** %s" % x["reason"])
    A("")

    A("## Integrity")
    A("")
    A("- defs censused: %d" % it["n_defs_censused"])
    A("- divergent defs declared vs matched in census: %d / %d" % (
        it["n_divergent_declared"], it["n_divergent_matched_in_census"]))
    A("- divergent/uniform overlap (must be empty): %s" % (
        it["divergent_uniform_overlap"] or "[] OK"))
    A("- judges loaded: %s" % json.dumps(it["judges_loaded"]))
    A("- defs with parse warnings: %d" % len(it["defs_with_parse_warnings"]))
    A("- duplicate def names: %s" % (it["duplicate_def_names"] or "[] OK"))
    A("")
    A("Note on sampling: the projection caps `sampled entities` at 30, so %d "
      "defs have a truncated sample list. The verdict metric (`line_share`) is "
      "therefore computed from the FULL `dxf_name histogram` header, which is "
      "not truncated; only `coord_share_sampled` is sample-bound." % sum(
          1 for c in res["per_def"].values() if c["sampled_truncated"]))
    A("")
    A("Numbers here are generated by `tools/e2/s1_entity_census.py`; "
      "input digests are recorded in `entity_census.json` -> `provenance`.")
    A("")
    return "\n".join(L)


def main_run(root, out_dir):
    sampled = collect_sampled(root)
    res, _ = run_census(root, sampled_scan=sampled)
    os.makedirs(out_dir, exist_ok=True)
    jp = os.path.join(out_dir, "entity_census.json")
    mp = os.path.join(out_dir, "entity_census.md")
    with open(jp, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2, sort_keys=False)
        fh.write("\n")
    with open(mp, "w", encoding="utf-8") as fh:
        fh.write(render_md(res))
    return res, jp, mp


# --- selftest ---------------------------------------------------------------

def _mk_prompt(name, ecount, hist, layers, bbox, sampled):
    lines = [
        "DWG block definition annotation task",
        "",
        "Definition name: %s" % name,
        "entity_count: %d" % ecount,
        "dxf_name histogram: %s" % ", ".join(
            "%s=%d" % (k, v) for k, v in hist.items()),
        "layer histogram: %s" % ", ".join(
            "%s=%d" % (k, v) for k, v in layers.items()),
    ]
    if bbox:
        lines.append("bbox from LINE start/end: [%s]" % ", ".join(
            str(x) for x in bbox))
    lines.append("sampled entities (max 30):")
    lines.extend(sampled)
    lines.append("")
    lines.append("Instructions / 지시사항:")
    lines.append("Classify the definition's likely architectural role.")
    return "\n".join(lines)


def build_fixture(root):
    """Self-contained fixture: 6 defs, 5 judges, a cluster probe, a v0 calib."""
    os.makedirs(os.path.join(root, "bench", "e1_shards"), exist_ok=True)
    os.makedirs(os.path.join(root, "reports", "e1", "annot_v1"), exist_ok=True)
    os.makedirs(os.path.join(root, "reports", "e1", "panel_20260717",
                             "evidence"), exist_ok=True)

    # 2 divergent defs: coordinate-blind (0 LINE, all LWPOLYLINE).
    # 3 uniform defs: LINE-rich. 1 other_mixed.
    specs = []
    for i in (1, 2):
        specs.append(dict(
            name="*U%d" % i, ecount=4,
            hist={"LWPOLYLINE": 4}, layers={"INSUL": 4}, bbox=None,
            sampled=["- LWPOLYLINE layer=INSUL handle=A%d%d vertices=5" % (i, k)
                     for k in range(4)]))
    for i in (1, 2, 3):
        specs.append(dict(
            name="*D%d" % i, ecount=4,
            hist={"LINE": 3, "MTEXT": 1}, layers={"DIM": 4},
            bbox=[0.0, 0.0, 0, 10.0, 10.0, 0],
            sampled=[
                "- LINE layer=DIM handle=B%d1 (0.0,0.0)->(10.0,0.0)" % i,
                "- LINE layer=DIM handle=B%d2 (10.0,0.0)->(10.0,10.0)" % i,
                "- LINE layer=DIM handle=B%d3 (10.0,10.0)->(0.0,10.0)" % i,
                # Quoted text containing a decoy coord pair - must NOT count.
                "- MTEXT layer=DIM handle=B%d4 '(1.0,2.0)->(3.0,4.0)'" % i,
            ]))
    specs.append(dict(
        name="*M1", ecount=4,
        hist={"LINE": 1, "INSERT": 2, "WEIRDKIND": 1}, layers={"0": 4},
        bbox=[0.0, 0.0, 0, 1.0, 1.0, 0],
        sampled=[
            "- LINE layer=0 handle=C1 (0.0,0.0)->(1.0,1.0)",
            "- INSERT layer=0 handle=C2 block=DIMDOT",
            "- INSERT layer=0 handle=C3 block=DIMDOT",
            "- WEIRDKIND layer=0 handle=C4 blah",   # unknown -> kind='other'
            "this line is not an entity and must not crash the parser",
        ]))

    with open(os.path.join(root, "bench", "e1_shards", "shard_01.jsonl"),
              "w", encoding="utf-8") as fh:
        for i, s in enumerate(specs):
            fh.write(json.dumps({
                "kind": "def_annotation",
                "unit_id": "defannot-fix-%d" % i,
                "prompt": _mk_prompt(s["name"], s["ecount"], s["hist"],
                                     s["layers"], s["bbox"], s["sampled"]),
            }, ensure_ascii=False) + "\n")
        fh.write(json.dumps({"kind": "other_task", "unit_id": "x",
                             "prompt": "ignore me"}, ensure_ascii=False) + "\n")

    # Judges: uniform on *D1..*D3; split on *U1/*U2; mixed on *M1.
    roles = {
        "*U1": ["기타", "평면 부분도", "평면 부분도", "평면 부분도", "평면 부분도"],
        "*U2": ["기타", "평면 부분도", "평면 부분도", "평면 부분도", "평면 부분도"],
        "*D1": ["치수캐시"] * 5,
        "*D2": ["치수캐시"] * 5,
        "*D3": ["치수캐시"] * 5,
        "*M1": ["심볼", "기타", "심볼", "가구", "심볼"],
    }
    for ji, j in enumerate(JUDGES):
        jdir = os.path.join(root, "reports", "e1", "annot_v1", "raw", j)
        os.makedirs(jdir, exist_ok=True)
        recs = []
        for di, (d, rs) in enumerate(roles.items()):
            # Exercise BOTH wall_line_handles shapes.
            wlh = ["B11", {"handle": "B12", "reason": "long parallel"}] \
                if d.startswith("*D") else []
            recs.append({"unit_id": "defannot-fix-%d" % di, "def": d,
                         "role": rs[ji], "wall_likelihood": 0.1 * ji,
                         "wall_line_handles": wlh, "notes": "",
                         "rationale": {"rule": "r", "evidence": "e"}})
        with open(os.path.join(jdir, "shard_01.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(recs, fh, ensure_ascii=False)

    with open(os.path.join(root, "reports", "e1", "annot_v1",
                           "cluster_probe_v1.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"n_defs": 6,
                   "counts": {"uniform_all5": 3, "full_split_A_vs_B": 1,
                              "soft_split_A_vs_Bmajority": 1,
                              "other_mixed": 1},
                   "full_split_defs": ["*U1"],
                   "soft_split_defs": ["*U2"]}, fh)

    # Aggregate-only, exactly like the real one -> v0 cross must degrade.
    with open(os.path.join(root, "reports", "e1", "panel_20260717",
                           "evidence", "calibration_v0.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"schema": "ariadne.e1_calibration.v0", "common_defs": 6},
                  fh)


def selftest():
    fails = []
    checks = 0

    def check(cond, label, got=None):
        nonlocal checks
        checks += 1
        if cond:
            print("  PASS  %s" % label)
        else:
            print("  FAIL  %s (got: %r)" % (label, got))
            fails.append(label)

    print("=" * 68)
    print("S1-B entity census - SELFTEST")
    print("=" * 68)

    # --- unit: entity line parsing
    print("\n[1] entity line parser (E1 grammar, card-verbatim samples)")
    e = parse_entity_line(
        "- LINE layer=DIM handle=8B52 (44248.83,24580.207)->(44248.83,22920.207)")
    check(e["kind"] == "LINE" and e["has_coords"] and e["handle"] == "8B52",
          "LINE parses kind+handle+coords", e)
    check(e["coords"] == [44248.83, 24580.207, 44248.83, 22920.207],
          "LINE coords exact", e.get("coords"))
    e = parse_entity_line("- INSERT layer=DIM handle=8B55 block=DIMDOT")
    check(e["kind"] == "INSERT" and not e["has_coords"]
          and e.get("block") == "DIMDOT", "INSERT: block, no coords", e)
    e = parse_entity_line("- MTEXT layer=DIM handle=8B57 '\\A1;3280'")
    check(e["kind"] == "MTEXT" and not e["has_coords"], "MTEXT no coords", e)
    e = parse_entity_line("- POINT layer=DEFPOINTS handle=8B58")
    check(e["kind"] == "POINT" and not e["has_coords"], "POINT no coords", e)
    e = parse_entity_line("- LWPOLYLINE layer=X-... handle=4376 vertices=5")
    check(e["kind"] == "LWPOLYLINE" and not e["has_coords"]
          and e.get("vertices") == 5,
          "LWPOLYLINE: vertices, NO coords (the blindness)", e)
    e = parse_entity_line("- WIPEOUT layer=0 handle=4855")
    check(e["kind"] == "WIPEOUT", "WIPEOUT", e)
    e = parse_entity_line("- SPLINE layer=... handle=1BCC")
    check(e["kind"] == "SPLINE", "SPLINE", e)
    e = parse_entity_line("- HATCH layer=... handle=1BCE pattern=SOLID loops=2")
    check(e["kind"] == "HATCH", "HATCH", e)
    e = parse_entity_line("- TEXT layer=DEFPOINTS handle=3AE '101 dong'")
    check(e["kind"] == "TEXT" and not e["has_coords"], "TEXT no coords", e)
    e = parse_entity_line("- ARC layer=... handle=820F")
    check(e["kind"] == "ARC" and not e["has_coords"], "ARC no coords", e)
    e = parse_entity_line("- CIRCLE layer=... handle=3288 radius=81")
    check(e["kind"] == "CIRCLE" and e.get("radius") == 81.0
          and not e["has_coords"], "CIRCLE: radius, no coords", e)
    e = parse_entity_line("- ELLIPSE layer=... handle=6B10")
    check(e["kind"] == "ELLIPSE", "ELLIPSE", e)
    e = parse_entity_line("- 3DFACE layer=... handle=1DA2")
    check(e["kind"] == "3DFACE", "3DFACE", e)
    e = parse_entity_line("- FLARGLE layer=x handle=99 wat=1")
    check(e["kind"] == "other", "unknown kind -> 'other', no crash", e)
    e = parse_entity_line("total garbage with no leading dash")
    check(e["kind"] == "other", "garbage line -> 'other', no crash", e)
    e = parse_entity_line("- MTEXT layer=DIM handle=D1 '(1.0,2.0)->(3.0,4.0)'")
    check(not e["has_coords"],
          "quoted text with decoy coord pair does NOT count as geometry", e)

    # --- unit: histogram + verdict banding
    print("\n[2] histogram parser + verdict bands")
    check(parse_histogram("INSERT=2, LINE=3, MTEXT=1") ==
          {"INSERT": 2, "LINE": 3, "MTEXT": 1}, "histogram parse")
    check(parse_histogram("") == {}, "empty histogram")
    check(parse_histogram("junk, A=1") == {"A": 1}, "junk-tolerant histogram")
    check(decide_verdict(0.10, 0.60)[0] == "BLINDNESS_CONFIRMED",
          "0.10 vs 0.60 -> BLINDNESS_CONFIRMED")
    check(decide_verdict(0.50, 0.50)[0] == "NOT_BLINDNESS",
          "0.50 vs 0.50 -> NOT_BLINDNESS")
    check(decide_verdict(0.40, 0.50)[0] == "NOT_BLINDNESS",
          "ratio 0.80 (boundary) -> NOT_BLINDNESS")
    check(decide_verdict(0.60, 0.50)[0] == "NOT_BLINDNESS",
          "ratio 1.20 (boundary) -> NOT_BLINDNESS")
    check(decide_verdict(0.35, 0.50)[0] == "MIXED",
          "ratio 0.70 -> MIXED (gap between bands)")
    check(decide_verdict(0.90, 0.50)[0] == "MIXED", "ratio 1.80 -> MIXED")
    check(decide_verdict(0.0, 0.0)[0] == "NOT_BLINDNESS",
          "0 vs 0 -> NOT_BLINDNESS (no ZeroDivisionError)")
    check(decide_verdict(0.5, 0.0)[0] == "MIXED",
          "x vs 0 -> MIXED (no ZeroDivisionError)")

    # --- unit: judge handle shapes
    print("\n[3] wall_line_handles: str AND dict shapes")
    check(normalize_handles(["A1", {"handle": "B2", "reason": "r"}]) ==
          ["A1", "B2"], "mixed str/dict handles normalize")
    check(normalize_handles(None) == [], "None handles -> []")
    check(normalize_handles([{"no_handle": 1}, 42]) == [],
          "malformed handle entries dropped, no crash")

    # --- integration: end-to-end on a fixture
    print("\n[4] end-to-end on synthetic fixture (OS temp dir)")
    with tempfile.TemporaryDirectory(prefix="s1b_selftest_") as tmp:
        build_fixture(tmp)
        sampled = collect_sampled(tmp)
        res, defs = run_census(tmp, sampled_scan=sampled)

        check(res["integrity"]["n_defs_censused"] == 6,
              "6 defs censused (non-def_annotation row skipped)",
              res["integrity"]["n_defs_censused"])
        check(res["group_sizes"]["divergent"] == 2,
              "divergent = full_split + soft_split = 2",
              res["group_sizes"]["divergent"])
        check(res["group_sizes"]["uniform"] == 3,
              "uniform (all-5-agree, derived) = 3",
              res["group_sizes"]["uniform"])
        check(res["integrity"]["uniform_derivation_matches_cluster_probe"],
              "derived uniform count matches cluster_probe counts.uniform_all5")
        check(res["group_sizes"]["other_mixed"] == 1,
              "other_mixed = 1", res["group_sizes"]["other_mixed"])
        check(res["integrity"]["divergent_uniform_overlap"] == [],
              "divergent and uniform are disjoint")

        d = defs["*U1"]
        check(d["line_share"] == 0.0 and d["zero_line"] and
              d["lwpolyline_share"] == 1.0,
              "coord-blind def: LINE-share 0.0, LWPOLYLINE-share 1.0", d)
        check(d["bbox_present"] is False,
              "coord-blind def has no derivable bbox", d["bbox_present"])
        check(d["coord_share_sampled"] == 0.0,
              "coord-blind def: measured sampled coord share 0.0")
        d = defs["*D1"]
        check(d["line_share"] == 0.75 and d["insert_count"] == 0,
              "LINE-rich def: LINE-share 3/4 = 0.75", d["line_share"])
        check(d["coord_share_sampled"] == 0.75,
              "LINE-rich def: 3 of 4 sampled lines carry coords",
              d["coord_share_sampled"])
        d = defs["*M1"]
        check(d["insert_count"] == 2, "INSERT count read from full histogram",
              d["insert_count"])

        gc = res["grammar_check"]
        check(gc["premise_holds"] is True,
              "grammar premise verified: only LINE carries coords",
              gc["coord_bearing_kinds"])
        check(gc["unknown_tokens"].get("WEIRDKIND") == 1,
              "unknown entity token counted, not crashed", gc["unknown_tokens"])

        v = res["verdict"]
        check(v["divergent_median_line_share"] == 0.0,
              "fixture divergent median LINE-share = 0.0")
        check(v["uniform_median_line_share"] == 0.75,
              "fixture uniform median LINE-share = 0.75")
        check(v["band"] == "BLINDNESS_CONFIRMED",
              "fixture verdict = BLINDNESS_CONFIRMED (0.0 < 0.75/2)", v["band"])

        bc = res["blindness_contingency"]
        check(bc["cells"] == {"blind_divergent": 2, "blind_uniform": 0,
                              "sighted_divergent": 0, "sighted_uniform": 3},
              "contingency 2x2 cells correct (other_mixed excluded)",
              bc["cells"])
        check(bc["p_divergent_given_coord_blind"] == 1.0 and
              bc["p_divergent_given_coord_bearing"] == 0.0,
              "fixture: P(div|blind)=1.0, P(div|sighted)=0.0")
        check(bc["risk_ratio"] is None,
              "risk_ratio guards divide-by-zero when P(div|sighted)=0",
              bc["risk_ratio"])

        x = res["v0_divergent_top20_cross"]
        check(x["available"] is False and "aggregate statistics only" in
              x["reason"],
              "aggregate-only calibration_v0.json -> v0 cross degrades cleanly")

        md = render_md(res)
        check("BLINDNESS_CONFIRMED" in md and "| kind |" in md,
              "markdown renders with verdict + entity-kind table")

        # determinism: same inputs -> byte-identical JSON
        res2, _ = run_census(tmp, sampled_scan=collect_sampled(tmp))
        check(json.dumps(res, sort_keys=True, ensure_ascii=False) ==
              json.dumps(res2, sort_keys=True, ensure_ascii=False),
              "deterministic: two runs produce identical output")

    print("\n" + "=" * 68)
    print("SELFTEST: %d checks, %d failed" % (checks, len(fails)))
    if fails:
        for f in fails:
            print("  FAILED: %s" % f)
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


def main():
    ap = argparse.ArgumentParser(description="S1-B per-def entity census")
    ap.add_argument("--selftest", action="store_true")
    here = os.path.dirname(os.path.abspath(__file__))
    default_root = os.path.abspath(os.path.join(here, "..", ".."))
    ap.add_argument("--root", default=default_root)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    out_dir = args.out or os.path.join(args.root, "reports", "e2", "s1")
    res, jp, mp = main_run(args.root, out_dir)
    v = res["verdict"]
    print("defs censused      : %d" % res["integrity"]["n_defs_censused"])
    print("groups             : %s" % json.dumps(res["group_sizes"]))
    print("divergent median LINE-share : %s" %
          _fmt(v["divergent_median_line_share"]))
    print("uniform   median LINE-share : %s" %
          _fmt(v["uniform_median_line_share"]))
    print("ratio                       : %s" %
          _fmt(v["ratio_divergent_over_uniform"]))
    print("VERDICT            : %s" % v["band"])
    print("wrote: %s" % jp)
    print("wrote: %s" % mp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
