#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W2 — surrogate-independence audit (G2 gate; red-team ticket T1 sev 0.75).

Assembles the disagreement structure between the four truth surrogates the E2
program relies on, so that "passed several checks" can be weighted by how
independent those checks actually are:

  A. silver internal      — judge-judge agreement (E1.5 calibration + cluster probe)
  B. detector vs silver   — per-def Pearson on the real drawing (B5 + name-blind arm)
  C. detector vs synth    — per-handle P/R against generated truth (B2, S/F/M)
  D. detector vs metamorphic — invariance battery (B4 per transform)

Re-runnable fold: reads only committed evidence artifacts; prefers the
dual-arm real_defs_v2.json when present (name-blind decontamination), falls
back to v1 with status=PARTIAL.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def main() -> int:
    cal = _load(r"reports/e1/annot_v1/calibration_v1.json")
    cluster = _load(r"reports/e1/annot_v1/cluster_probe_v1.json")
    b4 = _load(r"reports/e2/s5/b4_fold_v1.json")
    real2 = _load(r"reports/e2/s4/real_defs_v2.json")
    real1 = _load(r"reports/e2/s4/real_defs_v1.json")
    real = real2 or real1

    evals = {}
    for tier in ("S", "F", "M"):
        ev = _load(rf"reports/e2/s4/eval_{tier}.json")
        if ev:
            evals[tier] = ev

    # A. silver internal structure
    pairwise = (cal or {}).get("pairwise", {})
    fam_claude = {"opus48_max", "sonnet5_xhigh"}
    fam_other = {"grok45_xhigh", "sol56_xhigh", "fable5_high"}
    within, across = [], []
    for pair, rec in pairwise.items():
        a, b = pair.split("|")
        r = rec.get("likelihood_pearson")
        if r is None:
            continue
        same_cluster = ({a, b} <= {"fable5_high", "sol56_xhigh"}) or (
            {a, b} <= {"opus48_max", "sonnet5_xhigh", "grok45_xhigh"})
        (within if same_cluster else across).append((pair, round(r, 4)))
    silver_internal = {
        "fleiss_kappa_role": (cal or {}).get("fleiss_kappa_role_live"),
        "top_tier_mean_likelihood_pearson": (cal or {}).get("top_tier_mean_likelihood_pearson"),
        "likelihood_pearson_within_cluster": within,
        "likelihood_pearson_across_cluster": across,
        "cluster_finding": (
            "E1.5 judges split into two vocabulary families (fable+sol vs opus+sonnet+grok) "
            "on one confusion cell; merged-vocab pairwise agreement 0.93-0.98 (cluster_probe_v1). "
            "5 judges are NOT 5 independent measurements — treat consensus as ~2 families."
        ),
        "verdict": "NOT_INDEPENDENT_WITHIN_FAMILIES",
    }

    # B. detector vs silver (real drawing, per-def)
    b5 = ((real or {}).get("summary") or {}).get("B5", {})
    det_vs_silver = {
        "pearson_full": b5.get("pearson_all_defs"),
        "pearson_nameblind": b5.get("pearson_nameblind_all_defs"),
        "pearson_full_vs_nameblind": b5.get("pearson_full_vs_nameblind"),
        "source": "real_defs_v2.json" if real2 else "real_defs_v1.json",
        "status": "COMPLETE" if real2 else "PARTIAL_PENDING_NAMEBLIND",
        "note": (
            "Low r (~0.3) means detector max-score and judge wall_likelihood measure "
            "different things on real defs -> they are LARGELY INDEPENDENT evidence axes. "
            "If pearson_nameblind ~= pearson_full, the correlation that does exist is NOT "
            "driven by both sides reading layer names (decontaminated)."
        ),
    }

    # C. detector vs synthetic truth
    det_vs_synth = {}
    for tier, ev in evals.items():
        micro = (ev.get("micro") or ev.get("summary", {}).get("micro") or {})
        if not micro:
            for key in ("full", "arms"):
                if key in ev and isinstance(ev[key], dict):
                    micro = ev[key].get("micro", {})
                    break
        det_vs_synth[tier] = micro or ev.get("full") or "see eval file"
    det_vs_synth["note"] = (
        "Synthetic truth is generator-defined (constructional), fully independent of "
        "layer names, judges, and the metamorphic battery; fidelity to real stats is "
        "the weak axis (B1 FAIL: KS 0.5792, TV 0.265 - M-tier PROVISIONAL)."
    )

    # D. detector vs metamorphic battery
    det_vs_meta = {
        "per_transform": {k: {kk: v[kk] for kk in ("mean_invariance", "verdict")}
                          for k, v in ((b4 or {}).get("transforms") or {}).items()},
        "note": (
            "Invariance is a self-consistency axis (no external labels). Its scale arm "
            "FAIL is a transform-design artifact, not detector pathology (b4_fold_v1)."
        ),
    }

    audit = {
        "schema": "ariadne.e2_independence_audit.v1",
        "gate": "G2 (PROGRAM_PLAN_v1); red-team T1 대리 한통속 sev 0.75",
        "surrogates": {
            "A_silver_internal": silver_internal,
            "B_detector_vs_silver": det_vs_silver,
            "C_detector_vs_synth": det_vs_synth,
            "D_detector_vs_metamorphic": det_vs_meta,
        },
        "interpretation_weights": {
            "silver_consensus": "count as ~2 independent families, not 5 judges",
            "synth_truth": "independent of names/judges; weakened by B1 fidelity FAIL",
            "metamorphic": "independent of all labels; scale arm excluded (design flaw)",
            "joint_pass_rule": (
                "A claim passing synth + metamorphic + silver counts as 3 quasi-independent "
                "confirmations ONLY where name-blind decontamination holds (see B)."
            ),
        },
        "status": "COMPLETE" if real2 else "PARTIAL (name-blind arm pending)",
    }
    out = os.path.join(ROOT, "reports", "e2", "w2_independence_audit_v1.json")
    json.dump(audit, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({
        "A_silver": silver_internal["verdict"],
        "B_det_vs_silver": {k: det_vs_silver[k] for k in
                            ("pearson_full", "pearson_nameblind", "status")},
        "D_invariance": {k: v["mean_invariance"] for k, v in
                         det_vs_meta["per_transform"].items()},
        "status": audit["status"],
    }, indent=1, ensure_ascii=False))
    print("->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
