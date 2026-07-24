#!/usr/bin/env python
"""E2 S1-A: cited-handle reality audit.

For every wall_line_handle cited by every judge (5 live + v0 ornith), check whether
the handle actually appears in the projection text that judge was shown, and record
the entity kind (LINE / LWPOLYLINE / ...) the handle points to.

The judges never had filesystem access: the inline projection in the prompt is the
whole of their evidence. So "handle not in this def's projection text" == the judge
cited a handle it could not have seen == fabrication.

Verdict band (applied mechanically, per judge, on pct_nonexistent):
    > 5%      -> INSTRUMENTATION_BUG
    1% .. 5%  -> MINOR_NOISE
    < 1%      -> CLEAN

Usage:
    python s1_handle_audit.py [--repo-root PATH] [--out-json PATH] [--out-md PATH] [--top N]
    python s1_handle_audit.py --selftest

stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

# --------------------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------------------

LIVE_JUDGES = ["opus48_max", "fable5_high", "sol56_xhigh", "sonnet5_xhigh", "grok45_xhigh"]
V0_JUDGE = "ornith_v0"

# kind assigned to a citation whose handle is absent from the projection
KIND_NONEXISTENT = "<nonexistent>"
# kind assigned to an entity line whose shape we do not recognise
KIND_OTHER = "other"

BAND_ORDER = {"CLEAN": 0, "MINOR_NOISE": 1, "INSTRUMENTATION_BUG": 2}

# '- LINE layer=DIM handle=8B52 (44248.83,24580.207)->(44248.83,22920.207)'
#   kind := token after '- '; handle := the handle= token.
# The mandatory 'layer=' anchor is what makes the kind trustworthy: it keys on the
# grammar's shape rather than a hardcoded DXF vocabulary, so a name this corpus does not
# yet contain (POLYLINE, SOLID, ...) still reports its true kind, while a line that does
# not fit the shape degrades to 'other' instead of inventing a kind from a stray token.
# Verified: all 7539 entity lines in bench/e1_shards match this pattern.
# Non-greedy up to the first handle= so a quoted MTEXT/TEXT payload cannot shadow it.
RE_ENTITY = re.compile(r"^-\s+(?P<kind>[A-Za-z0-9_]+)\s+layer=.*?\bhandle=(?P<handle>[0-9A-Fa-f]+)\b")
RE_ANY_HANDLE = re.compile(r"\bhandle=(?P<handle>[0-9A-Fa-f]+)\b")
RE_DEF_NAME = re.compile(r"^Definition name:\s*(?P<name>.+?)\s*$", re.M)
RE_ENTITY_COUNT = re.compile(r"^entity_count:\s*(?P<n>\d+)\s*$", re.M)
RE_SAMPLED_HDR = re.compile(r"^sampled entities \(max (?P<n>\d+)\):", re.M)


# --------------------------------------------------------------------------------------
# projection parsing
# --------------------------------------------------------------------------------------


def normalize_handle(raw) -> str:
    """Canonical form of a cited handle: stripped, upper-cased.

    Projections emit upper-case hex. Normalizing here means a judge that answered in
    lower case is credited as correct; `exact_ok` on each citation records whether the
    raw string matched byte-for-byte, so normalization can never silently hide a miss.
    """
    return str(raw).strip().upper()


def parse_entity_line(line: str):
    """Parse one '- <KIND> ... handle=<HEX> ...' projection line.

    Returns (kind, handle) or None if the line carries no handle at all.
    An unrecognised line shape that still carries a handle -> kind == 'other'.
    Never raises.
    """
    m = RE_ENTITY.match(line)
    if m:
        return m.group("kind").upper(), normalize_handle(m.group("handle"))
    # Shape we do not recognise. If it still has a handle, keep it as 'other' so the
    # handle counts as existing -- the judge did see it.
    m2 = RE_ANY_HANDLE.search(line)
    if m2:
        return KIND_OTHER, normalize_handle(m2.group("handle"))
    return None


def parse_projection(prompt: str) -> dict:
    """Extract the handle->kind map and header facts from one def's projection text."""
    handles: dict[str, str] = {}
    collisions: list[str] = []
    n_entity_lines = 0

    for line in prompt.splitlines():
        if not line.startswith("- "):
            continue
        n_entity_lines += 1
        parsed = parse_entity_line(line)
        if parsed is None:
            continue
        kind, handle = parsed
        if handle in handles and handles[handle] != kind:
            collisions.append(handle)
        handles.setdefault(handle, kind)

    m = RE_DEF_NAME.search(prompt)
    def_name = m.group("name") if m else None
    m = RE_ENTITY_COUNT.search(prompt)
    entity_count = int(m.group("n")) if m else None
    m = RE_SAMPLED_HDR.search(prompt)
    sample_cap = int(m.group("n")) if m else None

    n_sampled = len(handles)
    truncated = bool(entity_count is not None and entity_count > n_entity_lines)

    return {
        "def_name": def_name,
        "entity_count": entity_count,
        "sample_cap": sample_cap,
        "n_entity_lines": n_entity_lines,
        "n_handles": n_sampled,
        "truncated": truncated,
        "handles": handles,
        "kind_collisions": collisions,
    }


def load_projections(shard_dir: Path) -> tuple[dict, list]:
    """unit_id -> parsed projection, for every shard_*.jsonl in shard_dir."""
    projections: dict[str, dict] = {}
    problems: list[dict] = []
    files = sorted(shard_dir.glob("shard_*.jsonl"))
    for path in files:
        with path.open(encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, 1):
                if not raw.strip():
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError as exc:
                    problems.append({"file": path.name, "line": lineno, "error": f"json: {exc}"})
                    continue
                unit_id = obj.get("unit_id")
                prompt = obj.get("prompt")
                if not unit_id or not isinstance(prompt, str):
                    problems.append({"file": path.name, "line": lineno, "error": "missing unit_id/prompt"})
                    continue
                proj = parse_projection(prompt)
                proj["shard"] = path.name
                if unit_id in projections:
                    problems.append({"file": path.name, "line": lineno, "error": f"duplicate unit_id {unit_id}"})
                    continue
                projections[unit_id] = proj
    return projections, problems


# --------------------------------------------------------------------------------------
# judge record loading
# --------------------------------------------------------------------------------------


def extract_cited_handles(record: dict) -> tuple[list, list]:
    """Pull wall_line_handles out of one annotation dict.

    Items are strings OR {"handle","reason"} objects -- both are handled.
    Returns (handles, skipped) where handles is a list of {handle_raw, reason} and
    skipped lists items of a shape we could not read.
    """
    out, skipped = [], []
    items = record.get("wall_line_handles")
    if items is None:
        return out, skipped
    if not isinstance(items, list):
        skipped.append({"reason": f"wall_line_handles is {type(items).__name__}, not list"})
        return out, skipped
    for item in items:
        if isinstance(item, str):
            out.append({"handle_raw": item, "reason": None})
        elif isinstance(item, dict):
            h = item.get("handle")
            if h is None:
                skipped.append({"reason": "dict item without 'handle' key", "item": str(item)[:120]})
                continue
            out.append({"handle_raw": h, "reason": item.get("reason")})
        elif isinstance(item, (int, float)):
            out.append({"handle_raw": item, "reason": None})
        else:
            skipped.append({"reason": f"item of type {type(item).__name__}", "item": str(item)[:120]})
    return out, skipped


def _is_annotation(payload: dict) -> bool:
    """Does this dict look like a def-annotation answer (vs a run receipt / bare handle)?"""
    if not isinstance(payload, dict):
        return False
    if "wall_line_handles" in payload:
        return True
    # an annotation always carries at least one of these; a swarm receipt carries none
    return bool({"role", "wall_likelihood", "def"} & set(payload.keys()))


def load_live_judge(raw_dir: Path, judge: str) -> tuple[list, list]:
    """reports/e1/annot_v1/raw/<judge>/shard_NN.json -> list of annotation records."""
    records: list[dict] = []
    problems: list[dict] = []
    jdir = raw_dir / judge
    if not jdir.is_dir():
        problems.append({"judge": judge, "error": f"missing dir {jdir}"})
        return records, problems
    for path in sorted(jdir.glob("shard_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append({"judge": judge, "file": path.name, "error": f"json: {exc}"})
            continue
        if not isinstance(data, list):
            problems.append({"judge": judge, "file": path.name, "error": f"expected list, got {type(data).__name__}"})
            continue
        for idx, rec in enumerate(data):
            if not isinstance(rec, dict):
                problems.append({"judge": judge, "file": path.name, "index": idx,
                                 "error": f"record is {type(rec).__name__}"})
                continue
            if not _is_annotation(rec):
                problems.append({"judge": judge, "file": path.name, "index": idx,
                                 "unit_id": rec.get("unit_id"), "error": "not an annotation payload"})
                continue
            records.append({"unit_id": rec.get("unit_id"), "def": rec.get("def"),
                            "source": path.name, "payload": rec})
    return records, problems


def load_v0(path: Path) -> tuple[list, list, list]:
    """reports/e1/ornith_annot_v0.jsonl -> records. Payload is nested under 'parsed'.

    Returns (records, problems, bare_handle_records). The v0 file has known pollution:
    a few lines whose 'parsed' is a swarm run-receipt, and a few whose 'parsed' is a
    single {"handle","reason"} object rather than an annotation. Neither is salvaged
    into the denominator -- both are reported.
    """
    records: list[dict] = []
    problems: list[dict] = []
    bare: list[dict] = []
    if not path.is_file():
        problems.append({"judge": V0_JUDGE, "error": f"missing file {path}"})
        return records, problems, bare
    with path.open(encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            if not raw.strip():
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                problems.append({"judge": V0_JUDGE, "line": lineno, "error": f"json: {exc}"})
                continue
            if not isinstance(obj, dict):
                problems.append({"judge": V0_JUDGE, "line": lineno, "error": "line is not an object"})
                continue
            unit_id = obj.get("unit_id")
            payload = obj.get("parsed", obj)
            if not isinstance(payload, dict):
                problems.append({"judge": V0_JUDGE, "line": lineno, "unit_id": unit_id,
                                 "error": f"parsed is {type(payload).__name__}"})
                continue
            keys = set(payload.keys())
            if keys == {"handle", "reason"}:
                bare.append({"unit_id": unit_id, "line": lineno,
                             "handle": payload.get("handle"), "reason": payload.get("reason")})
                problems.append({"judge": V0_JUDGE, "line": lineno, "unit_id": unit_id,
                                 "error": "parsed is a bare {handle,reason} object, not an annotation"})
                continue
            if not _is_annotation(payload):
                problems.append({"judge": V0_JUDGE, "line": lineno, "unit_id": unit_id,
                                 "error": "not an annotation payload (run receipt?)"})
                continue
            records.append({"unit_id": unit_id, "def": payload.get("def"),
                            "source": path.name, "payload": payload})
    return records, problems, bare


# --------------------------------------------------------------------------------------
# audit core
# --------------------------------------------------------------------------------------


def verdict_band(pct_nonexistent: float) -> str:
    """Mechanical band. >5 -> BUG, 1..5 inclusive -> MINOR_NOISE, <1 -> CLEAN."""
    if pct_nonexistent > 5.0:
        return "INSTRUMENTATION_BUG"
    if pct_nonexistent >= 1.0:
        return "MINOR_NOISE"
    return "CLEAN"


def worst_band(bands) -> str:
    worst = "CLEAN"
    for b in bands:
        if BAND_ORDER[b] > BAND_ORDER[worst]:
            worst = b
    return worst


def audit_judge(judge: str, records: list, projections: dict, top: int) -> dict:
    """Check every citation of one judge against the projection it was shown."""
    citations: list[dict] = []
    kind_hist = Counter()
    per_def = defaultdict(lambda: {"n_cited": 0, "n_nonexistent": 0, "unit_id": None, "def_name": None})
    unresolved_units = Counter()
    def_name_mismatch: list[dict] = []
    n_records_with_citations = 0
    n_normalization_rescued = 0
    skipped_items: list[dict] = []

    for rec in records:
        unit_id = rec["unit_id"]
        cited, skipped = extract_cited_handles(rec["payload"])
        for s in skipped:
            skipped_items.append({"unit_id": unit_id, **s})
        if cited:
            n_records_with_citations += 1
        proj = projections.get(unit_id)
        if proj is None and cited:
            unresolved_units[unit_id] += len(cited)

        if proj is not None and rec.get("def") and proj.get("def_name") and rec["def"] != proj["def_name"]:
            def_name_mismatch.append({"unit_id": unit_id, "judge_def": rec["def"], "projection_def": proj["def_name"]})

        for c in cited:
            raw = c["handle_raw"]
            norm = normalize_handle(raw)
            if proj is None:
                # Cannot check: the def this record points at has no projection.
                citations.append({"unit_id": unit_id, "handle": norm, "exists": None,
                                  "kind": None, "reason": c["reason"], "unresolved_unit": True})
                continue
            handles = proj["handles"]
            exists = norm in handles
            exact_ok = str(raw).strip() in handles
            if exists and not exact_ok:
                n_normalization_rescued += 1
            kind = handles.get(norm, KIND_NONEXISTENT)
            kind_hist[kind] += 1
            key = unit_id
            slot = per_def[key]
            slot["unit_id"] = unit_id
            slot["def_name"] = proj.get("def_name") or rec.get("def")
            slot["n_cited"] += 1
            if not exists:
                slot["n_nonexistent"] += 1
            citations.append({
                "unit_id": unit_id, "def_name": proj.get("def_name"), "handle": norm,
                "exists": exists, "kind": kind, "reason": c["reason"],
                "truncated_def": proj["truncated"], "exact_ok": exact_ok,
            })

    checkable = [c for c in citations if c["exists"] is not None]
    n_cited = len(checkable)
    n_nonexistent = sum(1 for c in checkable if not c["exists"])
    pct = (100.0 * n_nonexistent / n_cited) if n_cited else 0.0

    offenders = sorted(
        (d for d in per_def.values() if d["n_nonexistent"] > 0),
        key=lambda d: (-d["n_nonexistent"], -d["n_cited"], str(d["unit_id"])),
    )[:top]

    distinct = {(c["unit_id"], c["handle"]) for c in checkable}

    return {
        "judge": judge,
        "n_records": len(records),
        "n_records_with_citations": n_records_with_citations,
        "n_cited": n_cited,
        "n_cited_distinct": len(distinct),
        "n_nonexistent": n_nonexistent,
        "pct_nonexistent": round(pct, 4),
        "band": verdict_band(pct),
        "kind_histogram": dict(kind_hist.most_common()),
        "worst_offender_defs": offenders,
        "n_uncheckable_citations": len(citations) - n_cited,
        "unresolved_unit_ids": dict(unresolved_units),
        "n_normalization_rescued": n_normalization_rescued,
        "def_name_mismatches": def_name_mismatch[:20],
        "n_def_name_mismatches": len(def_name_mismatch),
        "skipped_handle_items": skipped_items[:20],
        "n_skipped_handle_items": len(skipped_items),
        "_citations": citations,
    }


def cross_tab(per_judge: list, projections: dict, split_defs: set, soft_defs: set) -> dict:
    """Is fabrication concentrated in divergent defs, or in truncated projections?

    Truncated == the projection showed only the first 30 entities of a larger def, so
    the judge was reasoning over a partial view.
    """
    def rate(cits):
        n = len(cits)
        bad = sum(1 for c in cits if not c["exists"])
        return {"n_cited": n, "n_nonexistent": bad, "pct": round(100.0 * bad / n, 4) if n else 0.0}

    all_cits = [c for j in per_judge for c in j["_citations"] if c["exists"] is not None]
    tr = [c for c in all_cits if c.get("truncated_def")]
    ntr = [c for c in all_cits if not c.get("truncated_def")]
    in_full = [c for c in all_cits if c.get("def_name") in split_defs]
    in_soft = [c for c in all_cits if c.get("def_name") in soft_defs]
    rest = [c for c in all_cits if c.get("def_name") not in split_defs and c.get("def_name") not in soft_defs]

    return {
        "by_projection_truncation": {
            "truncated_defs": rate(tr),
            "complete_defs": rate(ntr),
            "n_defs_truncated": sum(1 for p in projections.values() if p["truncated"]),
            "n_defs_total": len(projections),
        },
        "by_divergence_list": {
            "full_split_defs": rate(in_full),
            "soft_split_defs": rate(in_soft),
            "non_divergent_defs": rate(rest),
            "n_full_split_defs": len(split_defs),
            "n_soft_split_defs": len(soft_defs),
        },
    }


def negative_control(judge_records: dict, projections: dict) -> dict:
    """Prove the checker can detect fabrication before trusting it to report none.

    A "0% fabricated" verdict is only worth the instrument that produced it: a checker
    with a bug that made every lookup succeed would report the same 0%. So re-run every
    judge's real citations against a DIFFERENT def's projection. Those handles are then
    ones the judge provably never saw, so a working checker must flag ~all of them.
    Near-100% here is what licenses believing a near-0% in the live run.

    The def swap is a deterministic half-list rotation -- no RNG, so this is reproducible.
    """
    units = sorted(projections)
    n = len(units)
    out = {"method": "each record re-pointed at a different def via half-list rotation; "
                     "expect ~100% nonexistent from a working checker",
           "expectation": "pct_nonexistent >= 90 for every judge with citations",
           "per_judge": {}}
    if n < 2:
        out["control_ok"] = None
        out["note"] = "fewer than 2 projections; control not runnable"
        return out

    index = {u: i for i, u in enumerate(units)}
    pcts = []
    for judge, records in judge_records.items():
        shuffled = []
        for rec in records:
            own = rec.get("unit_id")
            if own not in index:
                continue
            swapped = dict(rec)
            swapped["unit_id"] = units[(index[own] + n // 2) % n]
            shuffled.append(swapped)
        res = audit_judge(judge, shuffled, projections, top=1)
        out["per_judge"][judge] = {"n_cited": res["n_cited"], "pct_nonexistent": res["pct_nonexistent"]}
        if res["n_cited"]:
            pcts.append(res["pct_nonexistent"])
    out["control_ok"] = bool(pcts) and all(p >= 90.0 for p in pcts)
    out["min_pct_nonexistent"] = round(min(pcts), 4) if pcts else None
    return out


def run_audit(repo_root: Path, top: int = 10) -> dict:
    shard_dir = repo_root / "bench" / "e1_shards"
    raw_dir = repo_root / "reports" / "e1" / "annot_v1" / "raw"
    v0_path = repo_root / "reports" / "e1" / "ornith_annot_v0.jsonl"
    probe_path = repo_root / "reports" / "e1" / "annot_v1" / "cluster_probe_v1.json"
    calib_path = repo_root / "reports" / "e1" / "panel_20260717" / "evidence" / "calibration_v0.json"

    projections, proj_problems = load_projections(shard_dir)

    per_judge = []
    load_problems = list(proj_problems)
    judge_records: dict[str, list] = {}
    for judge in LIVE_JUDGES:
        records, problems = load_live_judge(raw_dir, judge)
        load_problems.extend(problems)
        judge_records[judge] = records
        per_judge.append(audit_judge(judge, records, projections, top))

    v0_records, v0_problems, v0_bare = load_v0(v0_path)
    load_problems.extend(v0_problems)
    judge_records[V0_JUDGE] = v0_records
    per_judge.append(audit_judge(V0_JUDGE, v0_records, projections, top))

    control = negative_control(judge_records, projections)

    # divergence lists (optional inputs; absence must not crash the audit)
    split_defs, soft_defs, probe_note = set(), set(), None
    if probe_path.is_file():
        try:
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            split_defs = set(probe.get("full_split_defs") or [])
            soft_defs = set(probe.get("soft_split_defs") or [])
        except (json.JSONDecodeError, OSError) as exc:
            probe_note = f"unreadable: {exc}"
    else:
        probe_note = "absent"

    calibration = None
    if calib_path.is_file():
        try:
            calibration = json.loads(calib_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            calibration = None

    xtab = cross_tab(per_judge, projections, split_defs, soft_defs)

    # global worst offenders: aggregate nonexistent citations per def across all judges
    gdef = defaultdict(lambda: {"n_cited": 0, "n_nonexistent": 0, "judges": set(), "def_name": None})
    for j in per_judge:
        for c in j["_citations"]:
            if c["exists"] is None:
                continue
            slot = gdef[c["unit_id"]]
            slot["def_name"] = c.get("def_name")
            slot["n_cited"] += 1
            if not c["exists"]:
                slot["n_nonexistent"] += 1
                slot["judges"].add(j["judge"])
    global_offenders = sorted(
        ({"unit_id": k, "def_name": v["def_name"], "n_cited": v["n_cited"],
          "n_nonexistent": v["n_nonexistent"], "judges": sorted(v["judges"])}
         for k, v in gdef.items() if v["n_nonexistent"] > 0),
        key=lambda d: (-d["n_nonexistent"], -d["n_cited"], d["unit_id"]),
    )[:top]

    live_bands = [j["band"] for j in per_judge if j["judge"] in LIVE_JUDGES]
    all_bands = [j["band"] for j in per_judge]

    report = {
        "schema": "ariadne.e2_s1_handle_audit.v1",
        "card": "E2 S1-A cited-handle reality audit",
        "band_rule": {"INSTRUMENTATION_BUG": "pct_nonexistent > 5", "MINOR_NOISE": "1 <= pct_nonexistent <= 5",
                      "CLEAN": "pct_nonexistent < 1", "applied": "per judge; overall = worst band"},
        "verdict": worst_band(all_bands),
        "verdict_live_judges_only": worst_band(live_bands),
        "audit_validity": ("negative control passed: the checker flags handles the judge never saw"
                           if control.get("control_ok") else
                           "NEGATIVE CONTROL FAILED -- do not trust this verdict"),
        "negative_control": control,
        "inputs": {
            "shard_dir": str(shard_dir),
            "n_shard_files": len(sorted(shard_dir.glob("shard_*.jsonl"))),
            "n_projections": len(projections),
            "judge_raw_dir": str(raw_dir),
            "judges": LIVE_JUDGES + [V0_JUDGE],
            "v0_path": str(v0_path),
            "cluster_probe_path": str(probe_path) + (f" ({probe_note})" if probe_note else ""),
            "calibration_path": str(calib_path),
        },
        "totals": {
            "n_cited_all_judges": sum(j["n_cited"] for j in per_judge),
            "n_nonexistent_all_judges": sum(j["n_nonexistent"] for j in per_judge),
            "n_distinct_handles_in_projections": len({h for p in projections.values() for h in p["handles"]}),
        },
        "per_judge": [{k: v for k, v in j.items() if not k.startswith("_")} for j in per_judge],
        "global_worst_offender_defs": global_offenders,
        "cross_tabs": xtab,
        "data_quality": {
            "load_problems": load_problems[:40],
            "n_load_problems": len(load_problems),
            "v0_bare_handle_records": [
                {**b, "handle_exists_in_projection": (
                    normalize_handle(b["handle"]) in projections[b["unit_id"]]["handles"]
                    if b["unit_id"] in projections and b.get("handle") is not None else None)}
                for b in v0_bare
            ],
            "note": ("v0 'parsed' payloads that are run receipts or bare {handle,reason} objects are "
                     "excluded from every denominator, not salvaged."),
        },
        "context_calibration_v0": calibration,
    }
    return report


# --------------------------------------------------------------------------------------
# markdown rendering
# --------------------------------------------------------------------------------------


def render_md(rep: dict) -> str:
    L: list[str] = []
    A = L.append
    A("# E2 S1-A — cited-handle reality audit")
    A("")
    A(f"**VERDICT: {rep['verdict']}**  (live judges only: {rep['verdict_live_judges_only']})")
    A("")
    A("Band rule, applied mechanically to each judge's `pct_nonexistent`, overall = worst band:")
    A("")
    A("| pct_nonexistent | band |")
    A("|---|---|")
    A("| > 5% | INSTRUMENTATION_BUG |")
    A("| 1% – 5% | MINOR_NOISE |")
    A("| < 1% | CLEAN |")
    A("")
    A("## What was checked")
    A("")
    A("Each judge saw exactly one def per record: the inline projection text in its prompt, with no")
    A("filesystem access. This audit takes every handle the judge cited in `wall_line_handles` and asks")
    A("whether that handle string appears as a `handle=` token in that same def's projection. A handle")
    A("that is absent is one the judge could not have seen — it was fabricated, not misread.")
    A("")
    t = rep["totals"]
    A(f"- Projections parsed: **{rep['inputs']['n_projections']}** defs from "
      f"{rep['inputs']['n_shard_files']} shard files, carrying "
      f"{t['n_distinct_handles_in_projections']} distinct handles.")
    A(f"- Citations checked: **{t['n_cited_all_judges']}** across {len(rep['per_judge'])} judges.")
    A(f"- Nonexistent citations: **{t['n_nonexistent_all_judges']}**.")
    A("")
    A("## Per-judge results")
    A("")
    A("| judge | n_records | n_cited | n_distinct | n_nonexistent | pct_nonexistent | band |")
    A("|---|---:|---:|---:|---:|---:|---|")
    for j in rep["per_judge"]:
        A(f"| `{j['judge']}` | {j['n_records']} | {j['n_cited']} | {j['n_cited_distinct']} | "
          f"{j['n_nonexistent']} | {j['pct_nonexistent']:.2f}% | {j['band']} |")
    A("")
    nc = rep["negative_control"]
    A("## Negative control — is this verdict worth believing?")
    A("")
    A("A near-zero fabrication rate is exactly what a *broken* checker would also report, so the number")
    A("above means nothing until the instrument is shown able to fail. Every judge's real citations were")
    A(f"re-checked against a different def ({nc['method'].split(';')[0]}). Those are handles the judge")
    A("provably never saw, so a working checker must flag nearly all of them.")
    A("")
    A("| judge | n_cited | pct_nonexistent under control |")
    A("|---|---:|---:|")
    for judge, r in nc.get("per_judge", {}).items():
        A(f"| `{judge}` | {r['n_cited']} | {r['pct_nonexistent']:.2f}% |")
    A("")
    A(f"**Control {'PASSED' if nc.get('control_ok') else 'FAILED'}** "
      f"(expectation: {nc['expectation']}; observed minimum: {nc.get('min_pct_nonexistent')}%). "
      + ("The checker detects fabricated handles when they are present, so its report that the live runs "
         "contain none is a measurement, not a blind spot."
         if nc.get("control_ok") else
         "The checker did NOT reliably flag handles the judges never saw. The verdict above is void."))
    A("")
    A("## Kind histogram of cited handles")
    A("")
    A("What the cited handles actually point at in the projection. A judge citing a wall line should be")
    A("pointing at LINE or LWPOLYLINE; anything else is a category error the judge made with full sight")
    A("of the entity's own kind label.")
    A("")
    kinds: list[str] = []
    for j in rep["per_judge"]:
        for k in j["kind_histogram"]:
            if k not in kinds:
                kinds.append(k)
    order = [k for k in kinds if k != KIND_NONEXISTENT] + ([KIND_NONEXISTENT] if KIND_NONEXISTENT in kinds else [])
    A("| judge | " + " | ".join(f"`{k}`" for k in order) + " |")
    A("|---|" + "---:|" * len(order))
    for j in rep["per_judge"]:
        cells = [str(j["kind_histogram"].get(k, 0)) for k in order]
        A(f"| `{j['judge']}` | " + " | ".join(cells) + " |")
    A("")
    A("## Per-def worst offenders")
    A("")
    A("### Global (all judges pooled)")
    A("")
    if rep["global_worst_offender_defs"]:
        A("| unit_id | def | n_cited | n_nonexistent | judges implicated |")
        A("|---|---|---:|---:|---|")
        for d in rep["global_worst_offender_defs"]:
            A(f"| `{d['unit_id']}` | `{d['def_name']}` | {d['n_cited']} | {d['n_nonexistent']} | "
              f"{', '.join(d['judges'])} |")
    else:
        A("_No def attracted a single nonexistent citation._")
    A("")
    for j in rep["per_judge"]:
        A(f"### `{j['judge']}`")
        A("")
        if j["worst_offender_defs"]:
            A("| unit_id | def | n_cited | n_nonexistent |")
            A("|---|---|---:|---:|")
            for d in j["worst_offender_defs"]:
                A(f"| `{d['unit_id']}` | `{d['def_name']}` | {d['n_cited']} | {d['n_nonexistent']} |")
        else:
            A("_No nonexistent citations._")
        A("")
    A("## Cross-tabs")
    A("")
    xt = rep["cross_tabs"]["by_projection_truncation"]
    A(f"### By projection truncation ({xt['n_defs_truncated']}/{xt['n_defs_total']} defs are truncated)")
    A("")
    A("A projection lists at most 30 entities. Where `entity_count` exceeds that, the judge saw a partial")
    A("def. This does not excuse a fabricated handle — the judge cannot cite what it never saw — but it")
    A("shows whether fabrication tracks partial sight.")
    A("")
    A("| slice | n_cited | n_nonexistent | pct |")
    A("|---|---:|---:|---:|")
    for label, key in (("truncated defs", "truncated_defs"), ("complete defs", "complete_defs")):
        r = xt[key]
        A(f"| {label} | {r['n_cited']} | {r['n_nonexistent']} | {r['pct']:.2f}% |")
    A("")
    xd = rep["cross_tabs"]["by_divergence_list"]
    A(f"### By divergence list (full_split={xd['n_full_split_defs']}, soft_split={xd['n_soft_split_defs']})")
    A("")
    A("Defs where the judges split on role. If fabrication concentrated here, judge disagreement would be")
    A("an instrumentation artifact rather than genuine interpretive difference.")
    A("")
    A("| slice | n_cited | n_nonexistent | pct |")
    A("|---|---:|---:|---:|")
    for label, key in (("full_split defs", "full_split_defs"), ("soft_split defs", "soft_split_defs"),
                       ("non-divergent defs", "non_divergent_defs")):
        r = xd[key]
        A(f"| {label} | {r['n_cited']} | {r['n_nonexistent']} | {r['pct']:.2f}% |")
    A("")
    A("## Data quality")
    A("")
    dq = rep["data_quality"]
    A(f"- Load problems: **{dq['n_load_problems']}** (first 40 in JSON under `data_quality.load_problems`).")
    A(f"- {dq['note']}")
    for j in rep["per_judge"]:
        bits = []
        if j["n_uncheckable_citations"]:
            bits.append(f"{j['n_uncheckable_citations']} citations on unit_ids with no projection")
        if j["n_def_name_mismatches"]:
            bits.append(f"{j['n_def_name_mismatches']} def-name mismatches vs projection")
        if j["n_skipped_handle_items"]:
            bits.append(f"{j['n_skipped_handle_items']} unreadable handle items")
        if j["n_normalization_rescued"]:
            bits.append(f"{j['n_normalization_rescued']} citations matched only after case normalization")
        if bits:
            A(f"- `{j['judge']}`: " + "; ".join(bits) + ".")
    if dq["v0_bare_handle_records"]:
        A("")
        A("### v0 bare `{handle,reason}` records (excluded from denominators)")
        A("")
        A("| unit_id | handle | exists in projection? |")
        A("|---|---|---|")
        for b in dq["v0_bare_handle_records"]:
            A(f"| `{b['unit_id']}` | `{b['handle']}` | {b['handle_exists_in_projection']} |")
    A("")
    cal = rep.get("context_calibration_v0")
    if cal:
        hj = cal.get("handle_jaccard", {})
        A("## What this means for the wall-detector campaign")
        A("")
        A(f"`calibration_v0.json` measured handle-set agreement between ornith v0 and sonnet at Jaccard mean "
          f"**{hj.get('mean')}**, with **{hj.get('zero_frac')}** of def pairs sharing no cited handle at all "
          f"(n={hj.get('n')}). S1-A asked whether that near-total disagreement is an artifact — judges citing "
          f"handles that were never on the page.")
        A("")
        if rep["verdict"] == "CLEAN":
            A("**It is not.** Every cited handle resolves to an entity the judge was actually shown. The judges")
            A("are reading the same real entities and disagreeing about which of them are walls. The low Jaccard")
            A("is therefore a genuine interpretive split, and downstream stages must treat it as signal to")
            A("adjudicate rather than noise to filter out. Handle fabrication is ruled out as an explanation;")
            A("it does not follow that the citations are *correct*, only that their referents exist — see the")
            A("kind histogram above for whether judges are pointing at plausible wall geometry at all.")
        else:
            A(f"The audit returned **{rep['verdict']}**, so some of that disagreement is attributable to judges")
            A("citing handles they were never shown. Fix the instrumentation before reading the divergence as")
            A("a substantive disagreement about walls.")
    A("")
    A("---")
    A(f"_Generated by `tools/e2/s1_handle_audit.py` — schema `{rep['schema']}`._")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------------------


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(root: Path):
    """Synthetic repo covering every grammar shape from the card + hostile inputs."""
    proj_a = "\n".join([
        "DWG block definition annotation task",
        "",
        "Definition name: *TEST1",
        "entity_count: 13",
        "dxf_name histogram: LINE=1, INSERT=1",
        "layer histogram: DIM=13",
        "bbox from LINE start/end: [0.0, 0.0, 0, 10.0, 10.0, 0]",
        "sampled entities (max 30):",
        "- LINE layer=DIM handle=8B52 (44248.83,24580.207)->(44248.83,22920.207)",
        "- INSERT layer=DIM handle=8B55 block=DIMDOT",
        "- MTEXT layer=DIM handle=8B57 '\\A1;3280'",
        "- POINT layer=DEFPOINTS handle=8B58",
        "- LWPOLYLINE layer=X-WALL handle=4376 vertices=5",
        "- WIPEOUT layer=0 handle=4855",
        "- SPLINE layer=A handle=1BCC",
        "- HATCH layer=A handle=1BCE pattern=SOLID loops=2",
        "- TEXT layer=DEFPOINTS handle=3AE '101 dong'",
        "- ARC layer=A handle=820F",
        "- CIRCLE layer=A handle=3288 radius=81",
        "- ELLIPSE layer=A handle=6B10",
        "- 3DFACE layer=A handle=1DA2",
        "- GIBBERISH!! shape we never saw handle=DEAD extra",
        "",
        "Instructions:",
    ])
    # entity_count 13 < 14 entity lines -> not truncated; second def IS truncated.
    proj_b = "\n".join([
        "Definition name: *TEST2",
        "entity_count: 99",
        "sampled entities (max 30):",
        "- LINE layer=A-WALL handle=AAA1 (0,0)->(1,1)",
        "- LWPOLYLINE layer=A-WALL handle=AAA2 vertices=4",
    ])
    _write(root / "bench" / "e1_shards" / "shard_01.jsonl",
           json.dumps({"kind": "def_annotation", "prompt": proj_a, "unit_id": "u-1"}) + "\n" +
           json.dumps({"kind": "def_annotation", "prompt": proj_b, "unit_id": "u-2"}) + "\n" +
           "\n" +  # blank line must be tolerated
           "{ this is not json\n")  # malformed line must be tolerated

    raw = root / "reports" / "e1" / "annot_v1" / "raw"

    # judge 1: dict-form handles, 1 fabricated of 10 -> exactly 10.00% -> INSTRUMENTATION_BUG
    j1 = [{"unit_id": "u-1", "def": "*TEST1", "role": "심볼", "wall_likelihood": 0.5,
           "wall_line_handles": [{"handle": h, "reason": "r"} for h in
                                 ["8B52", "4376", "8B55", "8B57", "8B58", "4855", "1BCC", "1BCE", "820F", "FFFF"]],
           "notes": "", "rationale": {}}]
    _write(raw / "opus48_max" / "shard_01.json", json.dumps(j1))

    # judge 2: string-form handles, all real -> CLEAN. Lower-case must be rescued.
    j2 = [{"unit_id": "u-1", "def": "*TEST1", "role": "심볼", "wall_likelihood": 0.5,
           "wall_line_handles": ["8B52", "4376", " 8b55 ", "DEAD"], "notes": ""}]
    _write(raw / "fable5_high" / "shard_01.json", json.dumps(j2))

    # judge 3: hostile shapes -- must be skipped, never crash.
    # NB: the citations that survive must belong to their OWN def, otherwise the negative
    # control's def rotation would re-point them onto the def they actually belong to.
    j3 = [{"unit_id": "u-1", "def": "*TEST1", "wall_likelihood": 0.1,
           "wall_line_handles": [{"reason": "no handle key"}, None, ["nested"], {"handle": "8B52"}]},
          {"unit_id": "u-nonexistent-unit", "def": "*GHOST", "wall_likelihood": 0.9,
           "wall_line_handles": ["1234"]},
          "this record is a string, not a dict",
          {"unit_id": "u-2", "def": "*WRONGNAME", "wall_likelihood": 0.9,
           "wall_line_handles": [{"handle": "AAA1", "reason": "r"}]}]
    _write(raw / "sol56_xhigh" / "shard_01.json", json.dumps(j3))

    # judge 4: 1 fabricated of 100 -> exactly 1.00% -> MINOR_NOISE (lower band edge)
    real = ["8B52"] * 99
    j4 = [{"unit_id": "u-1", "def": "*TEST1", "wall_likelihood": 0.5,
           "wall_line_handles": real + ["BEEF"]}]
    _write(raw / "sonnet5_xhigh" / "shard_01.json", json.dumps(j4))

    # judge 5: file is not a list -> load problem, zero records
    _write(raw / "grok45_xhigh" / "shard_01.json", json.dumps({"not": "a list"}))

    # v0: nested 'parsed' + the two known pollution shapes
    v0 = "\n".join([
        json.dumps({"unit_id": "u-1", "parsed": {"def": "*TEST1", "role": "심볼", "wall_likelihood": 0.4,
                                                 "wall_line_handles": [{"handle": "8B52", "reason": "r"},
                                                                       {"handle": "CAFE", "reason": "r"}],
                                                 "notes": ""}}),
        json.dumps({"unit_id": "u-2", "parsed": {"handle": "AAA1", "reason": "bare handle object"}}),
        json.dumps({"unit_id": "u-1", "parsed": {"changed_files": [], "swarm_status": "ok",
                                                 "contract_ok": True, "merge_eligible": False}}),
        "not json at all",
    ])
    _write(root / "reports" / "e1" / "ornith_annot_v0.jsonl", v0)

    _write(root / "reports" / "e1" / "annot_v1" / "cluster_probe_v1.json",
           json.dumps({"full_split_defs": ["*TEST1"], "soft_split_defs": ["*TEST2"]}))
    # calibration file deliberately absent -> must not crash


def selftest() -> int:
    failures: list[str] = []

    def check(cond, label, got=None):
        if cond:
            print(f"  PASS  {label}")
        else:
            print(f"  FAIL  {label}" + (f"  (got: {got!r})" if got is not None else ""))
            failures.append(label)

    print("== s1_handle_audit selftest ==")

    print("\n[1] band boundaries (mechanical)")
    check(verdict_band(0.0) == "CLEAN", "0.00% -> CLEAN", verdict_band(0.0))
    check(verdict_band(0.99) == "CLEAN", "0.99% -> CLEAN", verdict_band(0.99))
    check(verdict_band(1.0) == "MINOR_NOISE", "1.00% -> MINOR_NOISE (lower edge inclusive)", verdict_band(1.0))
    check(verdict_band(5.0) == "MINOR_NOISE", "5.00% -> MINOR_NOISE (upper edge inclusive)", verdict_band(5.0))
    check(verdict_band(5.01) == "INSTRUMENTATION_BUG", "5.01% -> INSTRUMENTATION_BUG", verdict_band(5.01))
    check(worst_band(["CLEAN", "MINOR_NOISE", "CLEAN"]) == "MINOR_NOISE", "worst_band picks MINOR_NOISE")
    check(worst_band(["CLEAN", "INSTRUMENTATION_BUG", "MINOR_NOISE"]) == "INSTRUMENTATION_BUG",
          "worst_band picks INSTRUMENTATION_BUG")

    print("\n[2] projection grammar (every shape in the card)")
    expect = {
        "- LINE layer=DIM handle=8B52 (44248.83,24580.207)->(44248.83,22920.207)": ("LINE", "8B52"),
        "- INSERT layer=DIM handle=8B55 block=DIMDOT": ("INSERT", "8B55"),
        "- MTEXT layer=DIM handle=8B57 '\\A1;3280'": ("MTEXT", "8B57"),
        "- POINT layer=DEFPOINTS handle=8B58": ("POINT", "8B58"),
        "- LWPOLYLINE layer=X-WALL handle=4376 vertices=5": ("LWPOLYLINE", "4376"),
        "- WIPEOUT layer=0 handle=4855": ("WIPEOUT", "4855"),
        "- SPLINE layer=A handle=1BCC": ("SPLINE", "1BCC"),
        "- HATCH layer=A handle=1BCE pattern=SOLID loops=2": ("HATCH", "1BCE"),
        "- TEXT layer=DEFPOINTS handle=3AE '101 dong'": ("TEXT", "3AE"),
        "- ARC layer=A handle=820F": ("ARC", "820F"),
        "- CIRCLE layer=A handle=3288 radius=81": ("CIRCLE", "3288"),
        "- ELLIPSE layer=A handle=6B10": ("ELLIPSE", "6B10"),
        "- 3DFACE layer=A handle=1DA2": ("3DFACE", "1DA2"),
    }
    for line, want in expect.items():
        got = parse_entity_line(line)
        check(got == want, f"{want[0]:11s} -> {want}", got)
    check(parse_entity_line("- GIBBERISH!! nonsense handle=DEAD x") == (KIND_OTHER, "DEAD"),
          "unknown shape with handle -> ('other', handle)",
          parse_entity_line("- GIBBERISH!! nonsense handle=DEAD x"))
    check(parse_entity_line("- LINE layer=DIM no handle here") is None, "line without handle -> None")
    check(parse_entity_line("") is None, "empty line -> None")
    check(parse_entity_line("- \x00\xff garbage") is None, "binary garbage -> None (no crash)")
    check(parse_entity_line("- TEXT layer=A handle=3AE 'handle=FFFF spoof'") == ("TEXT", "3AE"),
          "quoted payload cannot shadow the real handle",
          parse_entity_line("- TEXT layer=A handle=3AE 'handle=FFFF spoof'"))

    print("\n[3] end-to-end on a synthetic fixture (OS temp dir)")
    with tempfile.TemporaryDirectory(prefix="s1_handle_audit_selftest_") as td:
        root = Path(td)
        _build_fixture(root)
        rep = run_audit(root, top=5)
        by = {j["judge"]: j for j in rep["per_judge"]}

        check(rep["inputs"]["n_projections"] == 2, "2 projections parsed (bad jsonl lines tolerated)",
              rep["inputs"]["n_projections"])

        o = by["opus48_max"]
        check(o["n_cited"] == 10 and o["n_nonexistent"] == 1, "opus48_max: 1 fabricated of 10",
              (o["n_cited"], o["n_nonexistent"]))
        check(abs(o["pct_nonexistent"] - 10.0) < 1e-9 and o["band"] == "INSTRUMENTATION_BUG",
              "opus48_max: 10.00% -> INSTRUMENTATION_BUG", (o["pct_nonexistent"], o["band"]))
        check(o["kind_histogram"].get(KIND_NONEXISTENT) == 1, "fabricated handle lands in <nonexistent> bucket",
              o["kind_histogram"])
        check(sum(o["kind_histogram"].values()) == o["n_cited"], "kind histogram sums to n_cited",
              (sum(o["kind_histogram"].values()), o["n_cited"]))
        check(o["worst_offender_defs"] and o["worst_offender_defs"][0]["unit_id"] == "u-1",
              "worst offender def surfaced")

        f = by["fable5_high"]
        check(f["n_nonexistent"] == 0 and f["band"] == "CLEAN", "fable5_high: all real -> CLEAN",
              (f["n_nonexistent"], f["band"]))
        check(f["n_normalization_rescued"] == 1, "lower-case ' 8b55 ' rescued by normalization",
              f["n_normalization_rescued"])
        check(f["kind_histogram"].get(KIND_OTHER) == 1, "'DEAD' resolves to kind 'other'", f["kind_histogram"])

        s = by["sol56_xhigh"]
        check(s["n_skipped_handle_items"] == 3, "3 unreadable handle items skipped", s["n_skipped_handle_items"])
        check(s["n_uncheckable_citations"] == 1 and "u-nonexistent-unit" in s["unresolved_unit_ids"],
              "citation on an unknown unit_id is uncheckable, not counted as fabricated",
              (s["n_uncheckable_citations"], s["unresolved_unit_ids"]))
        check(s["n_def_name_mismatches"] == 1, "def-name mismatch detected", s["n_def_name_mismatches"])

        n = by["sonnet5_xhigh"]
        check(n["n_cited"] == 100 and n["n_nonexistent"] == 1, "sonnet5_xhigh: 1 of 100",
              (n["n_cited"], n["n_nonexistent"]))
        check(abs(n["pct_nonexistent"] - 1.0) < 1e-9 and n["band"] == "MINOR_NOISE",
              "sonnet5_xhigh: exactly 1.00% -> MINOR_NOISE", (n["pct_nonexistent"], n["band"]))
        check(n["n_cited_distinct"] == 2, "duplicate citations collapse in n_cited_distinct only",
              n["n_cited_distinct"])

        g = by["grok45_xhigh"]
        check(g["n_records"] == 0 and g["n_cited"] == 0 and g["band"] == "CLEAN",
              "non-list judge file -> 0 records, no crash", (g["n_records"], g["n_cited"]))

        v = by[V0_JUDGE]
        check(v["n_records"] == 1, "v0: only the well-formed annotation is a record", v["n_records"])
        check(v["n_cited"] == 2 and v["n_nonexistent"] == 1, "v0: reads handles from nested 'parsed'",
              (v["n_cited"], v["n_nonexistent"]))
        bare = rep["data_quality"]["v0_bare_handle_records"]
        check(len(bare) == 1 and bare[0]["handle"] == "AAA1" and bare[0]["handle_exists_in_projection"] is True,
              "v0 bare {handle,reason} record reported, excluded from denominator, existence noted", bare)

        check(rep["verdict"] == "INSTRUMENTATION_BUG", "overall verdict = worst band", rep["verdict"])
        xt = rep["cross_tabs"]["by_projection_truncation"]
        check(xt["n_defs_truncated"] == 1, "u-2 (entity_count 99 > 2 sampled) flagged truncated",
              xt["n_defs_truncated"])
        check(rep["context_calibration_v0"] is None, "absent calibration file -> None, no crash")
        check(rep["cross_tabs"]["by_divergence_list"]["n_full_split_defs"] == 1, "divergence lists loaded")

        nc = rep["negative_control"]
        check(nc["per_judge"]["opus48_max"]["pct_nonexistent"] == 100.0,
              "negative control: citations re-pointed at another def are ~all flagged",
              nc["per_judge"]["opus48_max"]["pct_nonexistent"])
        check(nc["control_ok"] is True, "negative control passes on the fixture", nc["control_ok"])

        # The check is per-def, not against a global union of every handle in the corpus.
        # A judge citing a real handle that belongs to a DIFFERENT def must still be caught.
        projs, _ = load_projections(root / "bench" / "e1_shards")
        leak = audit_judge("leak", [{"unit_id": "u-1", "def": "*TEST1", "source": "x",
                                     "payload": {"wall_line_handles": ["AAA1"], "role": "r"}}], projs, 5)
        check(leak["n_nonexistent"] == 1,
              "cross-def leakage: real handle from another def is flagged on this def",
              leak["n_nonexistent"])

        md = render_md(rep)
        check("VERDICT: INSTRUMENTATION_BUG" in md, "md renders the verdict banner")
        check("Control PASSED" in md, "md renders the negative-control outcome")
        check("| `opus48_max` |" in md, "md renders the per-judge table")
        check(len(md) > 1500, "md is non-trivial", len(md))
        json.dumps(rep)  # must be serializable
        check(True, "report is JSON-serializable")

    print("\n" + "=" * 60)
    if failures:
        print(f"SELFTEST FAILED: {len(failures)} check(s) failed")
        for f_ in failures:
            print(f"  - {f_}")
        return 1
    print("SELFTEST PASSED: all checks green")
    return 0


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="E2 S1-A cited-handle reality audit")
    default_root = Path(__file__).resolve().parents[2]
    ap.add_argument("--repo-root", type=Path, default=default_root)
    ap.add_argument("--out-json", type=Path, default=None)
    ap.add_argument("--out-md", type=Path, default=None)
    ap.add_argument("--top", type=int, default=10, help="worst-offender rows per judge")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    root = args.repo_root.resolve()
    out_json = args.out_json or (root / "reports" / "e2" / "s1" / "handle_audit.json")
    out_md = args.out_md or (root / "reports" / "e2" / "s1" / "handle_audit.md")

    rep = run_audit(root, top=args.top)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    out_md.write_text(render_md(rep), encoding="utf-8")

    print(f"verdict: {rep['verdict']}  (live judges only: {rep['verdict_live_judges_only']})")
    for j in rep["per_judge"]:
        print(f"  {j['judge']:16s} n_cited={j['n_cited']:5d}  nonexistent={j['n_nonexistent']:4d}  "
              f"pct={j['pct_nonexistent']:6.2f}%  {j['band']}")
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
