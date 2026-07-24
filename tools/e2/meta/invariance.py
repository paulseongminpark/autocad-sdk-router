#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S5-C: invariance metric harness + sentinels for metamorphic wall detection.

Predictions are detector CLI JSON shaped as:
  {"scores": {"per_handle": {handle: {"score": float}}}}
Binary wall label = score >= 0.5.

SEGMENT-IR / TRUTH-LEDGER contracts are documented for battery consumers; this
module consumes detector preds + optional truth ledgers only.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

SCORE_THRESHOLD = 0.5
WALL_SHARE_SENTINEL = 0.9

HandleMap = Union[str, Mapping[str, str], None]


def _per_handle(pred: Mapping[str, Any]) -> Dict[str, float]:
    """Extract handle -> score from detector CLI output JSON."""
    scores = pred.get("scores") if isinstance(pred, Mapping) else None
    if not isinstance(scores, Mapping):
        return {}
    per = scores.get("per_handle")
    if not isinstance(per, Mapping):
        return {}
    out: Dict[str, float] = {}
    for h, row in per.items():
        key = str(h)
        if isinstance(row, Mapping) and "score" in row:
            try:
                out[key] = float(row["score"])
            except (TypeError, ValueError):
                continue
        elif isinstance(row, (int, float)):
            out[key] = float(row)
    return out


def _is_wall(score: float) -> bool:
    return score >= SCORE_THRESHOLD


def wall_handles(pred: Mapping[str, Any]) -> Set[str]:
    """Handles predicted as wall (score >= 0.5)."""
    return {h for h, s in _per_handle(pred).items() if _is_wall(s)}


def wall_count(pred: Mapping[str, Any]) -> int:
    return len(wall_handles(pred))


def _resolve_handle_map(handle_map: HandleMap) -> Optional[Dict[str, str]]:
    """Return dict old->new, or None for identity mapping."""
    if handle_map is None:
        return None
    if isinstance(handle_map, str):
        if handle_map.lower() in ("identity", "id", ""):
            return None
        raise ValueError("handle_map string must be 'identity', got {!r}".format(handle_map))
    return {str(k): str(v) for k, v in handle_map.items()}


def compare(
    pred_before: Mapping[str, Any],
    pred_after: Mapping[str, Any],
    handle_map: HandleMap = "identity",
) -> Dict[str, Any]:
    """Compare binary wall preds before/after a transform.

    Handles in pred_before are mapped through handle_map to look up pred_after.
    Returns {"invariance": 0..1, "flips": [before_handles that flipped]}.
    """
    before = _per_handle(pred_before)
    after = _per_handle(pred_after)
    hmap = _resolve_handle_map(handle_map)

    # Compare on before handles that we can resolve after the map.
    keys: List[str] = sorted(before.keys())
    if not keys:
        # No scored handles before: vacuously invariant (but sentinel_zero catches).
        return {"invariance": 1.0, "flips": []}

    flips: List[str] = []
    compared = 0
    for h in keys:
        after_h = h if hmap is None else hmap.get(h)
        if after_h is None:
            # Unmapped handle: treat as flip (lost correspondence).
            flips.append(h)
            compared += 1
            continue
        b_wall = _is_wall(before[h])
        a_score = after.get(after_h, 0.0)
        a_wall = _is_wall(a_score)
        compared += 1
        if b_wall != a_wall:
            flips.append(h)

    if compared == 0:
        inv = 1.0
    else:
        inv = 1.0 - (len(flips) / float(compared))
    return {"invariance": float(inv), "flips": flips}


def sentinel_zero(pred: Mapping[str, Any]) -> bool:
    """True when detector predicts zero walls (trivial invariance risk)."""
    return wall_count(pred) == 0


def sentinel_all(pred: Mapping[str, Any], n_handles: int) -> bool:
    """True when wall-share > 0.9 (near-all-wall triviality).

    wall-share = wall_count / n_handles. n_handles must be > 0; if n_handles<=0
    the sentinel fires (degenerate corpus).
    """
    if n_handles <= 0:
        return True
    share = wall_count(pred) / float(n_handles)
    return share > WALL_SHARE_SENTINEL


def recall_floor(
    pred: Mapping[str, Any],
    truth_ledger: Optional[Mapping[str, Any]],
) -> Optional[float]:
    """Recall of predicted walls vs truth wall_handles_flat.

    Returns None when truth is absent / empty (caller skips floor check).
    """
    if truth_ledger is None:
        return None
    flat = truth_ledger.get("wall_handles_flat")
    if not isinstance(flat, Sequence) or isinstance(flat, (str, bytes)):
        return None
    truth_set = {str(h) for h in flat}
    if not truth_set:
        return None
    pred_walls = wall_handles(pred)
    hit = len(pred_walls & truth_set)
    return hit / float(len(truth_set))


def verdict(
    inv: float,
    zero_flag: bool,
    all_flag: bool,
    recall: Optional[float],
    *,
    band: float,
    floor: float,
) -> Dict[str, Any]:
    """Pass/fail verdict. band and floor are ARGUMENTS (prereg seals later).

    PASS needs: inv >= band AND not zero_flag AND not all_flag AND
    (recall >= floor when recall is not None).
    """
    reasons: List[str] = []
    if inv < band:
        reasons.append("invariance_below_band")
    if zero_flag:
        reasons.append("sentinel_zero")
    if all_flag:
        reasons.append("sentinel_all")
    if recall is not None and recall < floor:
        reasons.append("recall_below_floor")
    passed = len(reasons) == 0
    return {
        "pass": passed,
        "verdict": "PASS" if passed else "FAIL",
        "inv": float(inv),
        "band": float(band),
        "zero_flag": bool(zero_flag),
        "all_flag": bool(all_flag),
        "recall": recall,
        "floor": float(floor),
        "reasons": reasons,
    }


def _mk_pred(scores: Mapping[str, float]) -> Dict[str, Any]:
    return {
        "scores": {
            "per_handle": {h: {"score": float(s)} for h, s in scores.items()}
        }
    }


def run_selftest() -> int:
    """Fabricate before/after preds incl. zero-wall; assert sentinels catch it."""
    print("SELFTEST invariance.py begin")
    errors: List[str] = []

    # --- compare: identity map, one flip ---
    before = _mk_pred({"h1": 0.9, "h2": 0.1, "h3": 0.8})
    after_ok = _mk_pred({"h1": 0.95, "h2": 0.05, "h3": 0.7})
    r_ok = compare(before, after_ok, "identity")
    if r_ok["invariance"] != 1.0 or r_ok["flips"]:
        errors.append("identity no-flip expected inv=1.0, got {!r}".format(r_ok))

    after_flip = _mk_pred({"h1": 0.95, "h2": 0.05, "h3": 0.2})  # h3 wall->nonwall
    r_flip = compare(before, after_flip, handle_map=None)
    if abs(r_flip["invariance"] - (2.0 / 3.0)) > 1e-9 or r_flip["flips"] != ["h3"]:
        errors.append("one-flip expected inv=2/3 flips=[h3], got {!r}".format(r_flip))

    # --- compare: remapped handles ---
    after_mapped = _mk_pred({"A1": 0.9, "A2": 0.1, "A3": 0.8})
    r_map = compare(before, after_mapped, {"h1": "A1", "h2": "A2", "h3": "A3"})
    if r_map["invariance"] != 1.0 or r_map["flips"]:
        errors.append("handle_map compare expected inv=1.0, got {!r}".format(r_map))

    # --- sentinel_zero: zero-wall case MUST fire ---
    zero_pred = _mk_pred({"h1": 0.1, "h2": 0.0, "h3": 0.4})
    zflag = sentinel_zero(zero_pred)
    if not zflag:
        errors.append("sentinel_zero failed to catch zero-wall prediction")
    else:
        print("sentinel_zero caught zero-wall case: OK")

    empty_pred = {"scores": {"per_handle": {}}}
    if not sentinel_zero(empty_pred):
        errors.append("sentinel_zero failed on empty per_handle")

    # Non-zero should not fire
    if sentinel_zero(before):
        errors.append("sentinel_zero false positive on before")

    # --- sentinel_all: wall-share > 0.9 ---
    almost_all = _mk_pred({f"x{i}": 0.9 for i in range(10)})  # 10/10 = 1.0
    if not sentinel_all(almost_all, 10):
        errors.append("sentinel_all failed on wall-share=1.0")
    nine = _mk_pred({f"x{i}": (0.9 if i < 9 else 0.1) for i in range(10)})  # 0.9 exact
    # share > 0.9 required; exactly 0.9 must NOT fire
    if sentinel_all(nine, 10):
        errors.append("sentinel_all false positive at wall-share==0.9")
    ten_of_eleven = _mk_pred({f"x{i}": (0.9 if i < 10 else 0.1) for i in range(11)})
    # 10/11 ≈ 0.909 > 0.9
    if not sentinel_all(ten_of_eleven, 11):
        errors.append("sentinel_all failed on wall-share>0.9")

    # --- recall_floor ---
    truth = {
        "truth": "wall.v1",
        "drawing_id": "selftest",
        "walls": [
            {
                "id": "w1",
                "axis": [[0.0, 0.0], [1000.0, 0.0]],
                "thickness": 240.0,
                "layer": "WALL",
                "handles": ["h1", "h3"],
            }
        ],
        "openings": [],
        "wall_handles_flat": ["h1", "h3"],
    }
    # before predicts h1+h3 walls -> recall 1.0
    rec = recall_floor(before, truth)
    if rec != 1.0:
        errors.append("recall_floor expected 1.0, got {!r}".format(rec))
    # after_flip drops h3 -> recall 0.5
    rec2 = recall_floor(after_flip, truth)
    if abs(rec2 - 0.5) > 1e-9:
        errors.append("recall_floor expected 0.5, got {!r}".format(rec2))
    if recall_floor(before, None) is not None:
        errors.append("recall_floor(None truth) should be None")

    # --- verdict: bands as arguments ---
    # Good run
    v_pass = verdict(1.0, False, False, 1.0, band=0.95, floor=0.5)
    if not v_pass["pass"] or v_pass["verdict"] != "PASS":
        errors.append("verdict expected PASS, got {!r}".format(v_pass))

    # Zero-wall: even with inv=1.0 must FAIL
    v_zero = verdict(1.0, True, False, None, band=0.95, floor=0.5)
    if v_zero["pass"] or "sentinel_zero" not in v_zero["reasons"]:
        errors.append("verdict must FAIL on sentinel_zero, got {!r}".format(v_zero))
    else:
        print("verdict FAIL on zero-wall sentinel: OK")

    # Low invariance
    v_inv = verdict(0.5, False, False, 1.0, band=0.95, floor=0.5)
    if v_inv["pass"] or "invariance_below_band" not in v_inv["reasons"]:
        errors.append("verdict must FAIL below band, got {!r}".format(v_inv))

    # Low recall when truth given
    v_rec = verdict(1.0, False, False, 0.1, band=0.95, floor=0.5)
    if v_rec["pass"] or "recall_below_floor" not in v_rec["reasons"]:
        errors.append("verdict must FAIL below recall floor, got {!r}".format(v_rec))

    # No truth (recall=None): skip floor
    v_no_truth = verdict(1.0, False, False, None, band=0.95, floor=0.5)
    if not v_no_truth["pass"]:
        errors.append("verdict with recall=None should PASS, got {!r}".format(v_no_truth))

    # sentinel_all FAIL
    v_all = verdict(1.0, False, True, None, band=0.95, floor=0.5)
    if v_all["pass"] or "sentinel_all" not in v_all["reasons"]:
        errors.append("verdict must FAIL on sentinel_all, got {!r}".format(v_all))

    if errors:
        print("SELFTEST FAILED:")
        for e in errors:
            print("  -", e)
        return 1

    print("SELFTEST PASSED")
    print(
        "summary: compare ok; sentinel_zero catches zero-wall; "
        "sentinel_all >0.9; recall_floor; verdict band/floor args"
    )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="S5-C invariance metric + sentinels")
    p.add_argument(
        "--selftest",
        action="store_true",
        help="run fabricated before/after selftest (no I/O outside process)",
    )
    args = p.parse_args(list(argv) if argv is not None else None)
    if args.selftest:
        return run_selftest()
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
