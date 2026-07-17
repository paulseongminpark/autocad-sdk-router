#!/usr/bin/env python3
"""S1-E - listing-cap censoring probe (forensic).

Suspicion under test
--------------------
The E1 annotation prompt ends with:

    List up to 10 entity handles that look like wall lines, ...

so any judge row with len(wall_line_handles) == 10 may be a *cap artifact*
(the instruction clipped the answer) rather than a *measurement* (the judge
actually believed there were exactly 10 wall lines).

A second, independent censoring layer sits upstream of the judge: the
projection itself only shows

    sampled entities (max 30):

so for any definition with entity_count > 30 the judge physically cannot see
(let alone cite) the tail entities. Both layers are quantified here.

Preregistered verdict band (from the card, applied verbatim)
-----------------------------------------------------------
Among defs with n_handles > 0, share pinned at exactly 10:
    >= 0.5  -> CAP_CENSORED
    <= 0.2  -> NOT_CENSORED
    else    -> MIXED

Secondary (not part of the band): a pile-up at 10 is *necessary* but not
*sufficient* for censoring. If a def only exposed <= 10 wall-ish entities in
its projection, a 10-handle answer cannot have been clipped by the cap. The
"binding" analysis separates those cases.

Usage
-----
    python tools/e2/s1_censoring.py --selftest
    python tools/e2/s1_censoring.py --run [--root .]

stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter

SCHEMA = "ariadne.e2_s1_censoring.v1"

# --- the two censoring layers, as stated in the E1 prompt text -------------
LIST_CAP = 10      # "List up to 10 entity handles"
SAMPLE_CAP = 30    # "sampled entities (max 30):"

# preregistered bands
BAND_CENSORED = 0.5
BAND_NOT = 0.2

JUDGES = ["opus48_max", "fable5_high", "sol56_xhigh", "sonnet5_xhigh", "grok45_xhigh"]

# DXF names the E1 projection grammar is known to emit
KNOWN_DXF = {
    "LINE", "INSERT", "MTEXT", "POINT", "LWPOLYLINE", "WIPEOUT", "SPLINE",
    "HATCH", "TEXT", "ARC", "CIRCLE", "ELLIPSE", "3DFACE",
}

# Entities that could plausibly *be* a wall line if a judge cited them.
# LINE is the only shape carrying coordinates in the projection; LWPOLYLINE
# carries a vertex count but no coords, and is the other common wall carrier.
WALLISH_DXF = {"LINE", "LWPOLYLINE"}

# '- LINE layer=DIM handle=8B52 (x,y)->(x,y)'  /  '- POINT layer=DEFPOINTS handle=8B58'
# layer names may contain spaces, so match non-greedily up to ' handle='.
ENTITY_RE = re.compile(
    r"^-\s+(?P<dxf>\S+)\s+layer=(?P<layer>.*?)\s+handle=(?P<handle>[0-9A-Za-z]+)\s*(?P<rest>.*)$"
)
SAMPLED_HDR_RE = re.compile(r"^sampled entities \(max\s*(?P<cap>\d+)\)\s*:")
DEFNAME_RE = re.compile(r"^Definition name:\s*(?P<name>.+?)\s*$")
ENTCOUNT_RE = re.compile(r"^entity_count:\s*(?P<n>\d+)\s*$")


# ---------------------------------------------------------------- projection

def parse_projection(prompt):
    """Parse one E1 projection block. Never raises on odd input.

    Unknown line shapes inside the sampled-entities block -> kind='other'.
    """
    out = {
        "def": None,
        "entity_count": None,
        "sample_cap": None,
        "entities": [],
        "n_sampled": 0,
        "n_other_lines": 0,
        "unknown_dxf": [],
    }
    if not isinstance(prompt, str):
        return out

    in_sample = False
    for raw in prompt.splitlines():
        line = raw.rstrip()
        if not in_sample:
            m = DEFNAME_RE.match(line)
            if m:
                out["def"] = m.group("name")
                continue
            m = ENTCOUNT_RE.match(line)
            if m:
                out["entity_count"] = int(m.group("n"))
                continue
            m = SAMPLED_HDR_RE.match(line)
            if m:
                out["sample_cap"] = int(m.group("cap"))
                in_sample = True
            continue

        # inside the sampled-entities block
        if not line.strip():
            in_sample = False          # blank line ends the block
            continue
        if not line.lstrip().startswith("-"):
            in_sample = False          # next header (e.g. 'Instructions / ...')
            continue

        m = ENTITY_RE.match(line.strip())
        if not m:
            out["entities"].append({"kind": "other", "handle": None, "raw": line.strip()[:120]})
            out["n_other_lines"] += 1
            continue
        dxf = m.group("dxf").upper()
        if dxf not in KNOWN_DXF:
            out["unknown_dxf"].append(dxf)
        out["entities"].append({
            "kind": dxf,
            "layer": m.group("layer"),
            "handle": norm_handle(m.group("handle")),
        })

    out["n_sampled"] = len(out["entities"])
    return out


def norm_handle(h):
    if h is None:
        return None
    s = str(h).strip().strip("'\"`").upper()
    return s or None


# ---------------------------------------------------------------- judge rows

def extract_handles(raw):
    """wall_line_handles items are strings OR {'handle','reason'} objects."""
    if not isinstance(raw, list):
        return [], 0
    out, bad = [], 0
    for item in raw:
        if isinstance(item, str):
            h = norm_handle(item)
        elif isinstance(item, dict):
            h = norm_handle(item.get("handle"))
        else:
            h = None
        if h is None:
            bad += 1
            continue
        out.append(h)
    return out, bad


def load_shards(root):
    """unit_id -> projection facts."""
    d = os.path.join(root, "bench", "e1_shards")
    units = {}
    if not os.path.isdir(d):
        return units
    for fn in sorted(os.listdir(d)):
        if not (fn.startswith("shard_") and fn.endswith(".jsonl")):
            continue
        with open(os.path.join(d, fn), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                uid = rec.get("unit_id")
                if not uid:
                    continue
                proj = parse_projection(rec.get("prompt"))
                proj["shard"] = fn
                units[uid] = proj
    return units


def load_judge(root, judge):
    """unit_id -> raw annotation dict, for reports/e1/annot_v1/raw/<judge>/."""
    d = os.path.join(root, "reports", "e1", "annot_v1", "raw", judge)
    rows = {}
    if not os.path.isdir(d):
        return rows
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for rec in data:
            if isinstance(rec, dict) and rec.get("unit_id"):
                rows[rec["unit_id"]] = rec
    return rows


def load_v0(root):
    """v0 ornith baseline: {'parsed': {...}, 'unit_id': ...} per jsonl line."""
    p = os.path.join(root, "reports", "e1", "ornith_annot_v0.jsonl")
    rows = {}
    if not os.path.isfile(p):
        return rows
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            uid = rec.get("unit_id")
            parsed = rec.get("parsed")
            if uid and isinstance(parsed, dict):
                rows[uid] = parsed
    return rows


# ---------------------------------------------------------------- statistics

def band(share):
    if share is None:
        return "NO_DATA"
    if share >= BAND_CENSORED:
        return "CAP_CENSORED"
    if share <= BAND_NOT:
        return "NOT_CENSORED"
    return "MIXED"


def _share(num, den):
    return round(num / den, 4) if den else None


def summarize(rows, units, label):
    """rows: unit_id -> annotation dict (v0 'parsed' or v1 judge row)."""
    hist = Counter()
    n_pos = n_at_cap = n_over_cap = 0
    bad_items = 0
    dup_defs = 0
    n_no_answer = 0
    # strata by the *upstream* censoring layer
    strata = {"le30": {"pos": 0, "cap": 0}, "gt30": {"pos": 0, "cap": 0}}
    # cap-binding evidence, only meaningful for at-cap rows
    bind = {"wallish_gt_cap": 0, "wallish_le_cap": 0, "no_projection": 0}
    # handle provenance
    cited = fabricated = 0

    for uid, ann in rows.items():
        raw = ann.get("wall_line_handles")
        if not isinstance(raw, list):
            # Missing/!list key is "no answer", not "answered zero walls".
            # Folding it into the 0 bucket would overstate confident negatives.
            n_no_answer += 1
            continue
        n = len(raw)
        hist[n] += 1
        hs, bad = extract_handles(raw)
        bad_items += bad
        if len(set(hs)) != len(hs):
            dup_defs += 1

        proj = units.get(uid)
        ec = proj.get("entity_count") if proj else None
        vis = {e["handle"] for e in proj["entities"] if e.get("handle")} if proj else set()
        wallish = sum(1 for e in proj["entities"] if e["kind"] in WALLISH_DXF) if proj else 0

        for h in hs:
            if proj is None:
                continue
            if h in vis:
                cited += 1
            else:
                fabricated += 1

        if n > 0:
            n_pos += 1
            if ec is not None:
                strata["gt30" if ec > SAMPLE_CAP else "le30"]["pos"] += 1
        if n == LIST_CAP:
            n_at_cap += 1
            if ec is not None:
                strata["gt30" if ec > SAMPLE_CAP else "le30"]["cap"] += 1
            if proj is None:
                bind["no_projection"] += 1
            elif wallish > LIST_CAP:
                bind["wallish_gt_cap"] += 1
            else:
                bind["wallish_le_cap"] += 1
        if n > LIST_CAP:
            n_over_cap += 1

    share = _share(n_at_cap, n_pos)
    res = {
        "label": label,
        "n_units": len(rows),
        "n_answered": len(rows) - n_no_answer,
        "n_no_answer": n_no_answer,
        "n_with_projection": sum(1 for u in rows if u in units),
        "n_handles_hist": {str(k): hist[k] for k in sorted(hist)},
        "max_n_handles": max(hist) if hist else 0,
        "n_pos": n_pos,
        "n_at_cap": n_at_cap,
        "n_over_cap": n_over_cap,
        "share_at_cap_among_pos": share,
        "verdict": band(share),
        "malformed_handle_items": bad_items,
        "defs_with_duplicate_handles": dup_defs,
        "handles_cited_in_projection": cited,
        "handles_not_in_projection": fabricated,
        "fabricated_handle_share": _share(fabricated, cited + fabricated),
        "by_entity_count": {
            "le_30": {
                "n_pos": strata["le30"]["pos"],
                "n_at_cap": strata["le30"]["cap"],
                "share_at_cap_among_pos": _share(strata["le30"]["cap"], strata["le30"]["pos"]),
                "verdict": band(_share(strata["le30"]["cap"], strata["le30"]["pos"])),
            },
            "gt_30": {
                "n_pos": strata["gt30"]["pos"],
                "n_at_cap": strata["gt30"]["cap"],
                "share_at_cap_among_pos": _share(strata["gt30"]["cap"], strata["gt30"]["pos"]),
                "verdict": band(_share(strata["gt30"]["cap"], strata["gt30"]["pos"])),
            },
        },
        "cap_binding_at_cap_rows": dict(bind),
        "cap_binding_share": _share(bind["wallish_gt_cap"],
                                    bind["wallish_gt_cap"] + bind["wallish_le_cap"]),
    }
    return res


def percentiles(vals, ps=(50, 75, 90, 95, 99)):
    if not vals:
        return {}
    s = sorted(vals)
    out = {}
    for p in ps:
        k = (len(s) - 1) * p / 100.0
        lo, hi = int(k), min(int(k) + 1, len(s) - 1)
        out[f"p{p}"] = round(s[lo] + (s[hi] - s[lo]) * (k - lo), 2)
    return out


def projection_layer_stats(units):
    """Quantify censoring layer #2: the max-30 sampling cap in the projection."""
    ecs = [u["entity_count"] for u in units.values() if u.get("entity_count") is not None]
    total_e = sum(ecs)
    total_sampled = sum(u["n_sampled"] for u in units.values())
    n_gt = sum(1 for e in ecs if e > SAMPLE_CAP)
    hidden = sum(max(0, e - SAMPLE_CAP) for e in ecs)
    unknown = Counter()
    for u in units.values():
        unknown.update(u.get("unknown_dxf") or [])
    return {
        "sample_cap": SAMPLE_CAP,
        "n_defs": len(units),
        "n_defs_entity_count_gt_30": n_gt,
        "share_defs_truncated": _share(n_gt, len(ecs)),
        "total_entities_declared": total_e,
        "total_entities_sampled": total_sampled,
        "hidden_entities": hidden,
        "hidden_entity_share": _share(hidden, total_e),
        "max_entity_count": max(ecs) if ecs else 0,
        "entity_count_percentiles": percentiles(ecs),
        "unparsed_projection_lines": sum(u["n_other_lines"] for u in units.values()),
        "unknown_dxf_names": dict(unknown),
    }


def divergence_overlay(root, units, per_judge_rows):
    """Does the cap pile-up concentrate on the defs where judges disagreed?"""
    p = os.path.join(root, "reports", "e1", "annot_v1", "cluster_probe_v1.json")
    if not os.path.isfile(p):
        return {"available": False}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return {"available": False}
    full = set(d.get("full_split_defs") or [])
    soft = set(d.get("soft_split_defs") or [])
    if not full and not soft:
        return {"available": False}

    uid_def = {uid: u.get("def") for uid, u in units.items()}
    out = {"available": True, "n_full_split_defs": len(full), "n_soft_split_defs": len(soft),
           "by_judge": {}}
    for judge, rows in per_judge_rows.items():
        buckets = {"full_split": [0, 0], "soft_split": [0, 0], "rest": [0, 0]}  # [pos, at_cap]
        for uid, ann in rows.items():
            dn = uid_def.get(uid)
            raw = ann.get("wall_line_handles")
            n = len(raw) if isinstance(raw, list) else 0
            if n <= 0:
                continue
            key = "full_split" if dn in full else ("soft_split" if dn in soft else "rest")
            buckets[key][0] += 1
            if n == LIST_CAP:
                buckets[key][1] += 1
        out["by_judge"][judge] = {
            k: {"n_pos": v[0], "n_at_cap": v[1], "share_at_cap_among_pos": _share(v[1], v[0])}
            for k, v in buckets.items()
        }
    return out


# ---------------------------------------------------------------- analysis

def analyze(root, judges=JUDGES):
    units = load_shards(root)
    per_rows = {}
    v0 = load_v0(root)
    if v0:
        per_rows["ornith_v0"] = v0
    for j in judges:
        rows = load_judge(root, j)
        if rows:
            per_rows[j] = rows

    summaries = {name: summarize(rows, units, name) for name, rows in per_rows.items()}
    verdicts = {n: s["verdict"] for n, s in summaries.items()}
    return {
        "schema": SCHEMA,
        "params": {
            "list_cap": LIST_CAP,
            "sample_cap": SAMPLE_CAP,
            "band_cap_censored_gte": BAND_CENSORED,
            "band_not_censored_lte": BAND_NOT,
            "band_denominator": "defs with n_handles > 0",
            "wallish_dxf": sorted(WALLISH_DXF),
        },
        "prompt_evidence": {
            "list_cap_instruction": "List up to 10 entity handles that look like wall lines, with a one-phrase reason each.",
            "sample_cap_header": "sampled entities (max 30):",
        },
        "projection_layer": projection_layer_stats(units),
        "judges": summaries,
        "verdicts": verdicts,
        "divergence_overlay": divergence_overlay(root, units, per_rows),
    }


# ---------------------------------------------------------------- rendering

def render_md(res):
    L = []
    A = L.append
    A("# S1-E — listing-cap censoring probe")
    A("")
    A(f"Schema `{res['schema']}` · list cap **{res['params']['list_cap']}** · "
      f"sample cap **{res['params']['sample_cap']}**")
    A("")
    A("## Question")
    A("")
    A("The E1 prompt instructs: *\"" + res["prompt_evidence"]["list_cap_instruction"] + "\"*")
    A("")
    A("So a row with `len(wall_line_handles) == 10` may be an instruction artifact, not a")
    A("measurement. Band (preregistered): among defs with `n_handles > 0`, share pinned at")
    A(f"exactly 10 ≥ {res['params']['band_cap_censored_gte']} → CAP_CENSORED; "
      f"≤ {res['params']['band_not_censored_lte']} → NOT_CENSORED; else MIXED.")
    A("")

    A("## Verdicts")
    A("")
    A("`n_pos` = defs with n_handles > 0 (the band denominator). `no_ans` = rows with no")
    A("`wall_line_handles` key at all — counted apart from a deliberate empty list.")
    A("")
    A("| judge | answered | no_ans | n_pos | n@10 | share@10 | verdict |")
    A("|---|---:|---:|---:|---:|---:|---|")
    for n, s in res["judges"].items():
        A(f"| {n} | {s['n_answered']} | {s['n_no_answer']} | {s['n_pos']} | {s['n_at_cap']} | "
          f"{s['share_at_cap_among_pos'] if s['share_at_cap_among_pos'] is not None else '-'} "
          f"| **{s['verdict']}** |")
    A("")

    p = res["projection_layer"]
    A("## Censoring layer 2 — projection sampling (max 30)")
    A("")
    A(f"- defs: **{p['n_defs']}**, of which entity_count > 30: **{p['n_defs_entity_count_gt_30']}** "
      f"({p['share_defs_truncated']})")
    A(f"- entities declared: **{p['total_entities_declared']}**, shown: **{p['total_entities_sampled']}**")
    A(f"- hidden by the 30-cap: **{p['hidden_entities']}** ({p['hidden_entity_share']} of all entities)")
    A(f"- max entity_count: **{p['max_entity_count']}** · percentiles: {p['entity_count_percentiles']}")
    A(f"- unparsed projection lines: {p['unparsed_projection_lines']} · unknown dxf names: {p['unknown_dxf_names']}")
    A("")

    A("## Stratified by the upstream cap")
    A("")
    A("| judge | ≤30 n_pos | ≤30 share@10 | ≤30 verdict | >30 n_pos | >30 share@10 | >30 verdict |")
    A("|---|---:|---:|---|---:|---:|---|")
    for n, s in res["judges"].items():
        a = s["by_entity_count"]["le_30"]
        b = s["by_entity_count"]["gt_30"]
        A(f"| {n} | {a['n_pos']} | {a['share_at_cap_among_pos']} | {a['verdict']} "
          f"| {b['n_pos']} | {b['share_at_cap_among_pos']} | {b['verdict']} |")
    A("")

    A("## Does the cap actually bind?")
    A("")
    A("A row at exactly 10 is only *censored* if the projection exposed more than 10 wall-ish")
    A("(LINE/LWPOLYLINE) entities. Otherwise 10 was reachable without clipping.")
    A("")
    A("| judge | @10 rows | wall-ish > 10 (cap can bind) | wall-ish ≤ 10 (cap cannot bind) | binding share |")
    A("|---|---:|---:|---:|---:|")
    for n, s in res["judges"].items():
        b = s["cap_binding_at_cap_rows"]
        A(f"| {n} | {s['n_at_cap']} | {b['wallish_gt_cap']} | {b['wallish_le_cap']} "
          f"| {s['cap_binding_share']} |")
    A("")

    A("## Handle provenance")
    A("")
    A("| judge | cited handles in projection | not in projection | fabricated share | max n_handles | n>10 |")
    A("|---|---:|---:|---:|---:|---:|")
    for n, s in res["judges"].items():
        A(f"| {n} | {s['handles_cited_in_projection']} | {s['handles_not_in_projection']} "
          f"| {s['fabricated_handle_share']} | {s['max_n_handles']} | {s['n_over_cap']} |")
    A("")

    A("## n_handles distribution")
    A("")
    for n, s in res["judges"].items():
        A(f"- **{n}** (n={s['n_units']}): {s['n_handles_hist']}")
    A("")

    dv = res.get("divergence_overlay") or {}
    if dv.get("available"):
        A("## Divergence overlay (cluster_probe_v1)")
        A("")
        A(f"full_split_defs={dv['n_full_split_defs']} · soft_split_defs={dv['n_soft_split_defs']}")
        A("")
        A("| judge | full_split share@10 | soft_split share@10 | rest share@10 |")
        A("|---|---:|---:|---:|")
        for n, b in dv["by_judge"].items():
            A(f"| {n} | {b['full_split']['share_at_cap_among_pos']} "
              f"| {b['soft_split']['share_at_cap_among_pos']} "
              f"| {b['rest']['share_at_cap_among_pos']} |")
        A("")
    return "\n".join(L) + "\n"


def write_outputs(root, res):
    d = os.path.join(root, "reports", "e2", "s1")
    os.makedirs(d, exist_ok=True)
    pj = os.path.join(d, "censoring.json")
    pm = os.path.join(d, "censoring.md")
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(pm, "w", encoding="utf-8") as f:
        f.write(render_md(res))
    return pj, pm


# ---------------------------------------------------------------- selftest

_GRAMMAR = [
    "- LINE layer=DIM handle=8B52 (44248.83,24580.207)->(44248.83,22920.207)",
    "- INSERT layer=DIM handle=8B55 block=DIMDOT",
    "- MTEXT layer=DIM handle=8B57 '\\A1;3280'",
    "- POINT layer=DEFPOINTS handle=8B58",
    "- LWPOLYLINE layer=X-WALL PLAN handle=4376 vertices=5",
    "- WIPEOUT layer=0 handle=4855",
    "- SPLINE layer=A-1 handle=1BCC",
    "- HATCH layer=A-2 handle=1BCE pattern=SOLID loops=2",
    "- TEXT layer=DEFPOINTS handle=3AE '101 dong'",
    "- ARC layer=A-3 handle=820F",
    "- CIRCLE layer=A-4 handle=3288 radius=81",
    "- ELLIPSE layer=A-5 handle=6B10",
    "- 3DFACE layer=A-6 handle=1DA2",
]


def _mk_prompt(name, entity_count, entity_lines):
    return (
        "DWG block definition annotation task\n"
        f"Definition name: {name}\n"
        f"entity_count: {entity_count}\n"
        "dxf_name histogram: LINE=1\n"
        "layer histogram: A=1\n"
        "bbox from LINE start/end: [0, 0, 0, 1, 1, 0]\n"
        "sampled entities (max 30):\n"
        + "\n".join(entity_lines)
        + "\n\nInstructions / 지시사항:\n"
        "List up to 10 entity handles that look like wall lines, with a one-phrase reason each.\n"
    )


def _lines(prefix, n, layer="A-WALL"):
    return [f"- LINE layer={layer} handle={prefix}{i:03X} (0,{i})->(1,{i})" for i in range(n)]


def build_fixture(root):
    os.makedirs(os.path.join(root, "bench", "e1_shards"), exist_ok=True)
    os.makedirs(os.path.join(root, "reports", "e1"), exist_ok=True)

    # D_PARSE: 13 valid grammar lines + 1 garbage line -> 'other', never crash
    d_parse = _mk_prompt("*PARSE", 14, _GRAMMAR + ["- ??? totally unknown shape here"])
    d_small = _mk_prompt("*SMALL", 12, _lines("A", 12))     # 12 wall-ish visible, <=30
    d_big = _mk_prompt("*BIG", 50, _lines("B", 30))         # truncated: 20 hidden
    d_big2 = _mk_prompt("*BIG2", 40, _lines("C", 30))       # truncated: 10 hidden

    units = [
        ("u-parse", d_parse), ("u-small", d_small), ("u-big", d_big), ("u-big2", d_big2),
    ]
    with open(os.path.join(root, "bench", "e1_shards", "shard_01.jsonl"), "w", encoding="utf-8") as f:
        for uid, p in units:
            f.write(json.dumps({"kind": "def_annotation", "prompt": p, "unit_id": uid}) + "\n")

    def row(uid, handles):
        return {"unit_id": uid, "def": uid, "role": "r", "wall_likelihood": 0.5,
                "wall_line_handles": handles, "notes": "n", "rationale": {}}

    # jcap: every positive row pinned at 10 -> share 1.0 -> CAP_CENSORED
    # object-form handles here, to exercise the dict branch
    cap10_b = [{"handle": f"B{i:03X}", "reason": "wall"} for i in range(10)]
    cap10_c = [{"handle": f"C{i:03X}", "reason": "wall"} for i in range(10)]
    cap10_a = [f"A{i:03X}" for i in range(10)]                     # string form
    jcap = [row("u-parse", cap10_a), row("u-small", cap10_a),
            row("u-big", cap10_b), row("u-big2", cap10_c)]

    # jfree: 2,3,0,1 -> n_pos=3, at_cap=0 -> share 0.0 -> NOT_CENSORED
    jfree = [row("u-parse", ["8B52", "4376"]), row("u-small", ["A000", "A001", "A002"]),
             row("u-big", []), row("u-big2", ["C000"])]

    # jmix: 10,3,3,0 -> n_pos=3, at_cap=1 -> share 0.3333 -> MIXED
    jmix = [row("u-parse", cap10_a), row("u-small", ["A000", "A001", "A002"]),
            row("u-big", ["B000", "B001", "B002"]), row("u-big2", [])]

    for j, data in (("jcap", jcap), ("jfree", jfree), ("jmix", jmix)):
        d = os.path.join(root, "reports", "e1", "annot_v1", "raw", j)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "shard_01.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)

    # v0 baseline, 'parsed' wrapper; includes a null-parsed line to test tolerance
    with open(os.path.join(root, "reports", "e1", "ornith_annot_v0.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"unit_id": "u-parse", "parsed": {"def": "*PARSE", "role": "r",
                "wall_likelihood": 0.1, "wall_line_handles": []}}) + "\n")
        f.write(json.dumps({"unit_id": "u-small", "parsed": {"def": "*SMALL", "role": "r",
                "wall_likelihood": 0.9, "wall_line_handles": cap10_a}}) + "\n")
        f.write(json.dumps({"unit_id": "u-bad", "parsed": None}) + "\n")
        # parsed present but no wall_line_handles key -> "no answer", not "zero walls"
        f.write(json.dumps({"unit_id": "u-big", "parsed": {"def": "*BIG", "role": "r",
                "wall_likelihood": 0.5}}) + "\n")
        f.write("\n")  # blank line tolerance
    return root


def _chk(ok, msg, fails):
    print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    if not ok:
        fails.append(msg)


def selftest():
    root = tempfile.mkdtemp(prefix="s1e_censoring_selftest_")
    fails = []
    try:
        build_fixture(root)
        print(f"fixture: {root}")

        print("\n[1] projection grammar parsing")
        units = load_shards(root)
        _chk(len(units) == 4, f"4 units parsed (got {len(units)})", fails)
        pp = units["u-parse"]
        _chk(pp["def"] == "*PARSE", f"def name = *PARSE (got {pp['def']})", fails)
        _chk(pp["entity_count"] == 14, f"entity_count = 14 (got {pp['entity_count']})", fails)
        _chk(pp["sample_cap"] == 30, f"sample_cap = 30 (got {pp['sample_cap']})", fails)
        _chk(pp["n_sampled"] == 14, f"14 sampled lines (got {pp['n_sampled']})", fails)
        _chk(pp["n_other_lines"] == 1, f"1 unknown shape -> other (got {pp['n_other_lines']})", fails)
        kinds = {e["kind"] for e in pp["entities"]}
        _chk(kinds == KNOWN_DXF | {"other"}, f"all 13 grammar kinds + other (got {len(kinds)})", fails)
        _chk(pp["unknown_dxf"] == [], "no unknown dxf names among the 13", fails)
        lw = [e for e in pp["entities"] if e["kind"] == "LWPOLYLINE"][0]
        _chk(lw["layer"] == "X-WALL PLAN" and lw["handle"] == "4376",
             f"layer with spaces parsed (got layer={lw['layer']!r} handle={lw['handle']})", fails)
        _chk(units["u-big"]["n_sampled"] == 30, "u-big shows 30 of 50 entities", fails)

        print("\n[2] censoring layer 2 (projection max-30)")
        p = projection_layer_stats(units)
        _chk(p["n_defs_entity_count_gt_30"] == 2, f"2 defs > 30 (got {p['n_defs_entity_count_gt_30']})", fails)
        _chk(p["total_entities_declared"] == 116, f"116 declared (got {p['total_entities_declared']})", fails)
        _chk(p["hidden_entities"] == 30, f"30 hidden (got {p['hidden_entities']})", fails)
        _chk(p["hidden_entity_share"] == round(30 / 116, 4),
             f"hidden share {round(30/116,4)} (got {p['hidden_entity_share']})", fails)
        _chk(p["unparsed_projection_lines"] == 1, f"1 unparsed line (got {p['unparsed_projection_lines']})", fails)

        print("\n[3] preregistered verdict bands")
        res = analyze(root, judges=["jcap", "jfree", "jmix"])
        v = res["verdicts"]
        _chk(v.get("jcap") == "CAP_CENSORED", f"jcap (share 1.0) -> CAP_CENSORED (got {v.get('jcap')})", fails)
        _chk(v.get("jfree") == "NOT_CENSORED", f"jfree (share 0.0) -> NOT_CENSORED (got {v.get('jfree')})", fails)
        _chk(v.get("jmix") == "MIXED", f"jmix (share 0.333) -> MIXED (got {v.get('jmix')})", fails)
        jm = res["judges"]["jmix"]
        _chk(jm["n_pos"] == 3 and jm["n_at_cap"] == 1,
             f"jmix n_pos=3 n_at_cap=1 (got {jm['n_pos']},{jm['n_at_cap']})", fails)
        _chk(jm["share_at_cap_among_pos"] == 0.3333,
             f"jmix share=0.3333 (got {jm['share_at_cap_among_pos']})", fails)
        _chk(band(0.5) == "CAP_CENSORED" and band(0.2) == "NOT_CENSORED"
             and band(0.4999) == "MIXED" and band(0.2001) == "MIXED",
             "band edges: >=0.5 censored, <=0.2 not, else mixed", fails)

        print("\n[4] handle forms (string vs {'handle','reason'} object)")
        jc = res["judges"]["jcap"]
        _chk(jc["n_handles_hist"] == {"10": 4}, f"jcap all rows at 10 (got {jc['n_handles_hist']})", fails)
        _chk(jc["handles_not_in_projection"] == 10,
             f"u-parse's 10 A-handles absent from its projection (got {jc['handles_not_in_projection']})", fails)
        _chk(jc["handles_cited_in_projection"] == 30,
             f"30 object-form handles resolve to projection (got {jc['handles_cited_in_projection']})", fails)

        print("\n[5] cap-binding evidence")
        b = jc["cap_binding_at_cap_rows"]
        # u-parse has 2 wall-ish (LINE+LWPOLYLINE) <= 10 -> cannot bind
        # u-small (12), u-big (30), u-big2 (30) -> can bind
        _chk(b["wallish_gt_cap"] == 3, f"3 at-cap rows where cap can bind (got {b['wallish_gt_cap']})", fails)
        _chk(b["wallish_le_cap"] == 1, f"1 at-cap row where cap cannot bind (got {b['wallish_le_cap']})", fails)
        _chk(jc["cap_binding_share"] == 0.75, f"binding share 0.75 (got {jc['cap_binding_share']})", fails)

        print("\n[6] v0 baseline + tolerance to junk lines")
        _chk("ornith_v0" in res["judges"], "v0 baseline loaded as its own row", fails)
        v0 = res["judges"]["ornith_v0"]
        _chk(v0["n_units"] == 3, f"3 v0 rows loaded, null-parsed dropped (got {v0['n_units']})", fails)
        _chk(v0["n_no_answer"] == 1 and v0["n_answered"] == 2,
             f"missing wall_line_handles key -> no_answer=1, answered=2 "
             f"(got {v0['n_no_answer']},{v0['n_answered']})", fails)
        _chk(v0["n_handles_hist"] == {"0": 1, "10": 1},
             f"no-answer row NOT folded into the 0 bucket (got {v0['n_handles_hist']})", fails)
        _chk(v0["n_pos"] == 1 and v0["n_at_cap"] == 1,
             f"v0 n_pos=1 n_at_cap=1 -> share 1.0 (got {v0['n_pos']},{v0['n_at_cap']})", fails)
        _chk(v0["verdict"] == "CAP_CENSORED", f"v0 verdict CAP_CENSORED (got {v0['verdict']})", fails)

        print("\n[7] degenerate inputs never crash")
        _chk(parse_projection(None)["def"] is None, "parse_projection(None) -> empty, no crash", fails)
        _chk(parse_projection("")["n_sampled"] == 0, "parse_projection('') -> 0 entities", fails)
        _chk(parse_projection("- LINE no_layer_no_handle")["entities"][0]["kind"] == "other"
             if parse_projection("- LINE no_layer_no_handle")["entities"] else True,
             "malformed entity line -> kind=other", fails)
        _chk(extract_handles(None) == ([], 0), "extract_handles(None) -> ([],0)", fails)
        _chk(extract_handles(["A", {"handle": "B"}, 42, {"no": "handle"}]) == (["A", "B"], 2),
             "mixed/garbage handle items handled", fails)
        _chk(band(None) == "NO_DATA", "band(None) -> NO_DATA", fails)
        empty = analyze(tempfile.mkdtemp(prefix="s1e_empty_"))
        _chk(empty["judges"] == {}, "empty root -> no judges, no crash", fails)

        print("\n[8] renderers")
        md = render_md(res)
        _chk("CAP_CENSORED" in md and "| jcap |" in md, "markdown renders verdict table", fails)
        _chk(len(json.dumps(res)) > 0, "result is JSON-serializable", fails)

        print("\n" + "=" * 62)
        if fails:
            print(f"SELFTEST FAILED — {len(fails)} check(s):")
            for m in fails:
                print(f"  - {m}")
            return 1
        print("SELFTEST PASSED — all checks green")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="S1-E listing-cap censoring probe")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if not a.run:
        ap.print_help()
        return 2

    res = analyze(a.root)
    pj, pm = write_outputs(a.root, res)
    p = res["projection_layer"]
    print(f"defs={p['n_defs']} truncated_gt30={p['n_defs_entity_count_gt_30']} "
          f"hidden_entities={p['hidden_entities']} ({p['hidden_entity_share']})")
    print("verdicts (band: share@10 among n_handles>0):")
    for n, s in res["judges"].items():
        print(f"  {n:<14} n={s['n_units']:<4} n_pos={s['n_pos']:<4} n@10={s['n_at_cap']:<4} "
              f"share={s['share_at_cap_among_pos']} -> {s['verdict']}")
    print(f"wrote: {pj}")
    print(f"wrote: {pm}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
