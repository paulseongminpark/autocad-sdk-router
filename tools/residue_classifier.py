#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""residue_classifier: adjudicate a roundtrip's residue-kind SIGNATURE against a
baseline drawing, to answer the load-bearing generalization question
(prereg_R5a): does the target's residue composition draw ONLY from residue
classes already seen/legislated on the baseline (1.dwg), or does a NOVEL
unexplained residue class appear?

Grounded in the EXISTING pipeline output -- it does NOT re-derive residues:
  - interior_diff.json.by_kind_gap[kind] = {"a_count": census, "b_count": rebuild}.
    A kind's residue gap = b_count - a_count; gap == 0 means that kind roundtripped
    count-clean (every entity of that kind matched after the LEX quotients in
    tools/blockdef_diff._canonical_entity folded representation differences).
  - deferred.json = the out-of-class entities honestly deferred (no certified
    create op yet), keyed by kind. A kind that DROPS on rebuild (a>0, b==0) is
    legitimate ONLY if those entities appear in deferred.json; a drop with no
    deferral is a SILENT DROP (FM8 -- counted-as-applied when it was not).

The set of "known" residue classes is DERIVED FROM THE BASELINE, never hardcoded:
the baseline's own by_kind_gap IS 1.dwg's measured residue signature (on R4l:
block_reference / line / lwpolyline / solid / wipeout carried gaps; everything
else was clean). A target kind that carries a gap while the SAME kind was clean
on the baseline is NOVEL -- precisely "a residue class not already seen on 1.dwg".

Stdlib only. No engine/router/subprocess. Read utf-8-sig, write utf-8.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

SCHEMA = "ariadne.residue_classifier.v1"


def read_json(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path, obj):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def kind_gaps(interior_diff):
    """{kind: {"a": a_count, "b": b_count, "gap": b - a}} from by_kind_gap.

    Defensive: tolerates missing counts (treated as 0) and a missing by_kind_gap
    (returns {}). gap>0 = rebuild produced MORE of this kind than census;
    gap<0 = rebuild dropped some (candidate defer / loss)."""
    out = {}
    by_kind = (interior_diff or {}).get("by_kind_gap") or {}
    if not isinstance(by_kind, dict):
        return out
    for kind, counts in by_kind.items():
        if not isinstance(counts, dict):
            continue
        a = int(counts.get("a_count") or 0)
        b = int(counts.get("b_count") or 0)
        out[str(kind)] = {"a": a, "b": b, "gap": b - a}
    return out


def residue_kinds(interior_diff, *, min_abs_gap=1):
    """Kinds whose |gap| >= min_abs_gap -- i.e. that carry a count residue."""
    return {
        kind for kind, g in kind_gaps(interior_diff).items()
        if abs(g["gap"]) >= min_abs_gap
    }


def _deferred_kinds(deferred):
    """Set of entity kinds that appear in a deferred.json (list of records)."""
    kinds = set()
    if isinstance(deferred, list):
        for rec in deferred:
            if isinstance(rec, dict) and rec.get("kind"):
                kinds.add(str(rec["kind"]))
    return kinds


def classify(target_diff, baseline_diff, *, target_deferred=None, min_abs_gap=1):
    """Compare the target's residue-kind signature to the baseline's.

    Returns the full report dict (see module docstring / SCHEMA). The verdict is
    honest and terminal:
      - NOVEL_CLASS : a kind carries a gap on the target that was clean on the
                      baseline (an unexplained residue class -- prereg fail).
      - SILENT_DROP : a kind dropped on rebuild (a>0, b==0) without appearing in
                      deferred.json (FM8 -- a loss masqueraded as applied).
      - GENERALIZES : neither -- every residue kind is one the baseline already
                      carried, and every out-of-class drop is honestly deferred.
    SILENT_DROP takes precedence over NOVEL_CLASS in the single-word verdict
    because an integrity breach (fake-applied) is more severe than an
    explainable-but-new class; both are always reported in full regardless.
    """
    base_kinds = residue_kinds(baseline_diff, min_abs_gap=min_abs_gap)
    tgt = kind_gaps(target_diff)
    deferred_kinds = _deferred_kinds(target_deferred)

    target_residue = []
    novel = []
    for kind in sorted(tgt):
        g = tgt[kind]
        if abs(g["gap"]) < min_abs_gap:
            continue
        klass = "known" if kind in base_kinds else "novel"
        row = {"kind": kind, "a_count": g["a"], "b_count": g["b"],
               "gap": g["gap"], "klass": klass}
        target_residue.append(row)
        if klass == "novel":
            novel.append(kind)

    # deferred integrity: a kind fully dropped on rebuild (had entities in
    # census, none in rebuild) must be accounted for in deferred.json.
    dropped_kinds = [k for k, g in sorted(tgt.items())
                     if g["a"] > 0 and g["b"] == 0]
    undeferred_drops = [k for k in dropped_kinds if k not in deferred_kinds]
    deferred_ok = not undeferred_drops

    novel_found = bool(novel)
    if not deferred_ok:
        verdict = "SILENT_DROP"
    elif novel_found:
        verdict = "NOVEL_CLASS"
    else:
        verdict = "GENERALIZES"

    return {
        "schema": SCHEMA,
        "verdict": verdict,
        "novel_class_found": novel_found,
        "target_interior_diff0_fraction":
            ((target_diff or {}).get("totals") or {}).get("interior_diff0_fraction"),
        "baseline_interior_diff0_fraction":
            ((baseline_diff or {}).get("totals") or {}).get("interior_diff0_fraction"),
        "baseline_residue_kinds": sorted(base_kinds),
        "target_residue_kinds": target_residue,
        "novel_residue_kinds": sorted(novel),
        "deferred_integrity": {
            "dropped_kinds": dropped_kinds,
            "deferred_kinds": sorted(deferred_kinds),
            "undeferred_drops": sorted(undeferred_drops),
            "ok": deferred_ok,
        },
        "min_abs_gap": min_abs_gap,
    }


def _print_summary(report):
    print("residue_classifier verdict: %s (novel_class_found=%s)"
          % (report["verdict"], report["novel_class_found"]))
    print("  target diff0_fraction  : %s" % report["target_interior_diff0_fraction"])
    print("  baseline residue kinds : %s" % ", ".join(report["baseline_residue_kinds"]))
    for row in report["target_residue_kinds"]:
        flag = "  <<< NOVEL" if row["klass"] == "novel" else ""
        print("  %-16s a=%-6d b=%-6d gap=%+d  [%s]%s"
              % (row["kind"], row["a_count"], row["b_count"], row["gap"],
                 row["klass"], flag))
    di = report["deferred_integrity"]
    if not di["ok"]:
        print("  SILENT DROP (undeferred): %s" % ", ".join(di["undeferred_drops"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Classify a roundtrip's residue-kind "
                                 "signature against a baseline drawing.")
    ap.add_argument("--target", required=True, help="target interior_diff.json")
    ap.add_argument("--baseline", required=True, help="baseline (1.dwg) interior_diff.json")
    ap.add_argument("--deferred", default=None, help="target deferred.json (out-of-class)")
    ap.add_argument("--out", default=None, help="output report JSON path")
    ap.add_argument("--min-abs-gap", type=int, default=1)
    args = ap.parse_args(argv)

    target_diff = read_json(args.target)
    baseline_diff = read_json(args.baseline)
    target_deferred = read_json(args.deferred) if args.deferred and os.path.exists(args.deferred) else None

    report = classify(target_diff, baseline_diff,
                      target_deferred=target_deferred, min_abs_gap=args.min_abs_gap)
    if args.out:
        write_json(args.out, report)
    _print_summary(report)
    # exit 2 on a non-generalizing verdict so a sweep/CI can gate on it (honest,
    # never renamed): NOVEL_CLASS or SILENT_DROP both fail the generalization.
    return 0 if report["verdict"] == "GENERALIZES" else 2


if __name__ == "__main__":
    sys.exit(main())
