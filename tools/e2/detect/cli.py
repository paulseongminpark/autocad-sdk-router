#!/usr/bin/env python3
"""E2 / S4 detector CLI + eval harness.

Wires the sibling S4 modules (normalize, insert_expand, unit_anchor,
evidence_grid) *by file path* via importlib — the modules must NOT import
each other; cli.py is the single wiring point (dependency injection).

Module dirs are plain script dirs: there is deliberately NO __init__.py.

Subcommands
-----------
detect  --dxf P --out O.json [--no-layer-channel]
        Build SEG-IR (normalize modelspace + insert_expand INSERT tree),
        infer scale via unit_anchor, score via evidence_grid.
        Writes {"seg_ir": ..., "scores": ...}.

eval    --pred O.json --truth T.json --out E.json [--threshold F]
        Per-handle precision/recall/F1 against TRUTH-LEDGER v1
        wall_handles_flat, plus a per-evidence-channel ablation table.
        Pure: needs no sibling modules.

--selftest
        Build a small DXF with ezdxf in the OS temp dir (LINEs + LWPOLYLINE
        + ARC + a nested INSERT; 2 walls + 1 door). If all siblings exist,
        run detect+eval end-to-end; otherwise degrade to a wiring check.
        Always exercises the (self-contained) eval path. Writes
        reports/e2/s4/selftest_demo.json with whatever ran.

Graceful degradation: if a sibling module is missing at import time, the
command prints which one(s) and exits 3 (parallel build tolerated).

Python: stdlib only, except ezdxf (ALLOWED for this card, selftest only).
"""

import argparse
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Contract constants -------------------------------------------------------
SEG_IR_VERSION = "seg.v1"
TRUTH_VERSION = "wall.v1"
EVIDENCE_CHANNELS = ("parallel", "thickness", "junction", "layer")
DEFAULT_THRESHOLD = 0.5
EXIT_MISSING_SIBLING = 3

SIBLINGS_FOR_DETECT = ("normalize", "insert_expand", "unit_anchor", "evidence_grid")


# --- sibling loading (importlib by file path, no package imports) --------
def load_sibling(modname):
    """Load a sibling module by file path. Returns module or None if absent.

    Raises on a present-but-broken module so import errors are loud (R5).
    """
    path = os.path.join(HERE, modname + ".py")
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def require_siblings(names):
    """Load the named siblings. Returns (mods_dict, missing_list)."""
    mods, missing = {}, []
    for n in names:
        m = load_sibling(n)
        if m is None:
            missing.append(n)
        else:
            mods[n] = m
    return mods, missing


def _die_missing(missing):
    sys.stderr.write(
        "MISSING SIBLING MODULE(S): " + ", ".join(missing) + "\n"
        "(parallel build: expected to appear later; cannot run this command yet)\n"
    )
    return EXIT_MISSING_SIBLING


# --- SEG-IR helpers -------------------------------------------------------
def seg_ir_skeleton(drawing_id):
    return {
        "ir": SEG_IR_VERSION,
        "drawing_id": drawing_id,
        "units": "unknown",
        "scale_mm_per_unit": None,
        "segments": [],
    }


def _coerce_segment(seg):
    """Normalize a segment-dict to the exact SEG-IR v1 segment keys."""
    return {
        "sid": seg.get("sid"),
        "handle": seg.get("handle"),
        "pts": seg.get("pts"),
        "layer": seg.get("layer", ""),
        "kind": seg.get("kind", "line"),
        "label": seg.get("label", "unknown"),
        "source": seg.get("source", "native"),
    }


def merge_seg_ir(base, extra):
    """Merge two SEG-IR dicts into one, re-numbering sids to stay unique.

    base wins on scalar fields (ir/drawing_id/units); scale is taken from
    whichever side has a non-null value.
    """
    base = base or {}
    extra = extra or {}
    out = seg_ir_skeleton(base.get("drawing_id") or extra.get("drawing_id") or "unknown")
    out["ir"] = base.get("ir") or extra.get("ir") or SEG_IR_VERSION
    # units: prefer a concrete value over "unknown"
    for side in (base, extra):
        u = side.get("units")
        if u and u != "unknown":
            out["units"] = u
            break
    # scale: first non-null
    for side in (base, extra):
        s = side.get("scale_mm_per_unit")
        if s is not None:
            out["scale_mm_per_unit"] = s
            break

    segs = []
    for side in (base, extra):
        for seg in (side.get("segments") or []):
            segs.append(_coerce_segment(seg))
    # unique sequential sids
    for i, seg in enumerate(segs, start=1):
        seg["sid"] = "s%04d" % i
    out["segments"] = segs
    return out


# --- detect pipeline ------------------------------------------------------
def run_detect(dxf_path, no_layer_channel, mods):
    """Wire the siblings into a SEG-IR + scores product.

    mods: dict with keys normalize / insert_expand / unit_anchor / evidence_grid.
    """
    normalize = mods["normalize"]
    insert_expand = mods["insert_expand"]
    unit_anchor = mods["unit_anchor"]
    evidence_grid = mods["evidence_grid"]

    drawing_id = os.path.splitext(os.path.basename(dxf_path))[0]

    # 1) modelspace (inserts NOT expanded here) ...
    base_ir = normalize.parse_modelspace(dxf_path, expand_inserts=False)
    if not isinstance(base_ir, dict):
        base_ir = seg_ir_skeleton(drawing_id)

    # 2) ... plus the INSERT tree, expanded via the INJECTED converter.
    insert_ir = insert_expand.expand(dxf_path, normalize.entity_to_segments)
    if not isinstance(insert_ir, dict):
        insert_ir = seg_ir_skeleton(drawing_id)

    seg_ir = merge_seg_ir(base_ir, insert_ir)
    if not seg_ir.get("drawing_id") or seg_ir["drawing_id"] == "unknown":
        seg_ir["drawing_id"] = drawing_id

    # 3) scale via unit_anchor — adopt only geometrically anchored scales.
    # INSUNITS-header-only inference reports confidence 0.45 by design (weak);
    # adopting it unconditionally shrank the thickness band 1000x on metre-flagged
    # drawings and zeroed the parallel channel (W1 B2 S-tier forensics, 2026-07-17).
    anchor = unit_anchor.infer_from_dxf(dxf_path) or {}
    if anchor.get("scale_mm_per_unit") is not None and anchor.get("confidence", 0.0) >= 0.5:
        seg_ir["scale_mm_per_unit"] = anchor["scale_mm_per_unit"]

    # 4) scores via evidence_grid; --no-layer-channel disables the layer channel
    params = None
    if no_layer_channel:
        params = {"use_layer": False}
    scores = evidence_grid.score(seg_ir, params=params)
    if not isinstance(scores, dict):
        scores = {"per_handle": {}, "walls": []}
    # attach the unit-anchor evidence alongside (non-contract, informational)
    scores["unit_anchor"] = anchor

    return {"seg_ir": seg_ir, "scores": scores}


# --- eval harness (pure) --------------------------------------------------
def _prf(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def _score_from_channels(evidence, exclude=None):
    """Mean of the evidence channel values, optionally excluding one channel."""
    vals = []
    for ch in EVIDENCE_CHANNELS:
        if exclude is not None and ch == exclude:
            continue
        v = evidence.get(ch)
        if isinstance(v, (int, float)):
            vals.append(float(v))
    return (sum(vals) / len(vals)) if vals else 0.0


def _predicted_handles_from_walls(scores):
    """Union of handles across scores['walls'] (the detector's positive set)."""
    handles = set()
    for wall in (scores.get("walls") or []):
        for h in (wall.get("handles") or []):
            if h:
                handles.add(str(h))
    return handles


def _predicted_from_evidence(per_handle, threshold, exclude=None):
    """Positive handle set by thresholding the (optionally ablated) channel mean."""
    pos = set()
    for h, rec in (per_handle or {}).items():
        if not h:
            continue
        ev = (rec or {}).get("evidence") or {}
        if _score_from_channels(ev, exclude=exclude) >= threshold:
            pos.add(str(h))
    return pos


def _metrics_for(predicted, truth):
    predicted, truth = set(predicted), set(truth)
    tp = len(predicted & truth)
    fp = len(predicted - truth)
    fn = len(truth - predicted)
    return _prf(tp, fp, fn)


def run_eval(pred, truth, threshold=DEFAULT_THRESHOLD):
    """Per-handle P/R/F1 vs TRUTH-LEDGER wall_handles_flat + ablation table."""
    scores = pred.get("scores") or {}
    per_handle = scores.get("per_handle") or {}

    truth_handles = set(str(h) for h in (truth.get("wall_handles_flat") or []) if h)
    drawing_id = truth.get("drawing_id") or (pred.get("seg_ir") or {}).get("drawing_id") or "unknown"

    # Baseline = detector's own positive set (scores.walls); fall back to
    # thresholded per-handle score if no walls were emitted.
    predicted = _predicted_handles_from_walls(scores)
    baseline_source = "walls"
    if not predicted and per_handle:
        predicted = set(
            str(h) for h, rec in per_handle.items()
            if h and isinstance((rec or {}).get("score"), (int, float)) and rec["score"] >= threshold
        )
        baseline_source = "per_handle.score>=threshold"

    baseline = _metrics_for(predicted, truth_handles)
    baseline.update({
        "source": baseline_source,
        "predicted": sorted(predicted),
        "truth": sorted(truth_handles),
    })

    # Ablation: recompute predictions from the evidence channels, full then
    # with one channel removed at a time; delta_f1 = full - ablated.
    ablation = []
    full_pred = _predicted_from_evidence(per_handle, threshold, exclude=None)
    full_metrics = _metrics_for(full_pred, truth_handles)
    ablation.append({
        "channel_removed": "none",
        "n_predicted": len(full_pred),
        **{k: full_metrics[k] for k in ("tp", "fp", "fn", "precision", "recall", "f1")},
        "delta_f1": 0.0,
    })
    for ch in EVIDENCE_CHANNELS:
        abl_pred = _predicted_from_evidence(per_handle, threshold, exclude=ch)
        m = _metrics_for(abl_pred, truth_handles)
        ablation.append({
            "channel_removed": ch,
            "n_predicted": len(abl_pred),
            **{k: m[k] for k in ("tp", "fp", "fn", "precision", "recall", "f1")},
            "delta_f1": round(full_metrics["f1"] - m["f1"], 6),
        })

    return {
        "drawing_id": drawing_id,
        "threshold": threshold,
        "n_handles_scored": len(per_handle),
        "baseline": baseline,
        "ablation": ablation,
    }


# --- selftest -------------------------------------------------------------
def _build_selftest_dxf(path):
    """Build a small DXF: 2 wall entities + 1 door (nested INSERT).

    Returns a summary dict (handles, entity kinds) or raises.
    """
    import ezdxf

    doc = ezdxf.new(setup=True)
    doc.header["$INSUNITS"] = 4  # 4 = millimeters
    msp = doc.modelspace()

    summary = {"native_entities": [], "insert": None, "insunits": 4}

    # Wall 1 : a LINE on layer WALL
    l1 = msp.add_line((0, 0), (5000, 0), dxfattribs={"layer": "WALL"})
    summary["native_entities"].append({"kind": "LINE", "layer": "WALL", "handle": l1.dxf.handle})

    # Wall 2 : an LWPOLYLINE on layer WALL (offset parallel run + a return)
    lw = msp.add_lwpolyline(
        [(0, 3000), (5000, 3000), (5000, 6000)],
        dxfattribs={"layer": "WALL"},
    )
    summary["native_entities"].append({"kind": "LWPOLYLINE", "layer": "WALL", "handle": lw.dxf.handle})

    # A stray ARC on a non-wall layer (curvature evidence surface)
    arc = msp.add_arc(center=(2500, 1500), radius=800, start_angle=0, end_angle=90,
                      dxfattribs={"layer": "DETAIL"})
    summary["native_entities"].append({"kind": "ARC", "layer": "DETAIL", "handle": arc.dxf.handle})

    # Door : an inner block (leaf + swing arc), nested inside an outer block,
    # placed once via an INSERT in modelspace (nested INSERT tree).
    leaf = doc.blocks.new(name="DOOR_LEAF")
    leaf.add_line((0, 0), (900, 0), dxfattribs={"layer": "DOOR"})
    leaf.add_arc(center=(0, 0), radius=900, start_angle=0, end_angle=90,
                 dxfattribs={"layer": "DOOR"})

    assembly = doc.blocks.new(name="DOOR_ASSEMBLY")
    # nested: the assembly INSERTs the leaf with rotation+offset
    assembly.add_blockref("DOOR_LEAF", (100, 0), dxfattribs={"rotation": 15})

    ins = msp.add_blockref(
        "DOOR_ASSEMBLY", (5000, 0),
        dxfattribs={"rotation": 30, "xscale": 1.0, "yscale": 1.0},
    )
    summary["insert"] = {
        "block": "DOOR_ASSEMBLY", "nested_block": "DOOR_LEAF",
        "handle": ins.dxf.handle, "rotation": 30, "insert_at": [5000, 0],
    }

    doc.saveas(path)
    return summary


def run_selftest(out_report_path):
    result = {
        "card": "S4-E",
        "component": "tools/e2/detect/cli.py",
        "python": sys.version.split()[0],
        "mode": None,             # "full" | "wiring_check"
        "fixture": None,
        "siblings_present": [],
        "siblings_missing": [],
        "detect": None,
        "eval": None,
        "eval_selfcheck": None,
        "wiring": {},
        "notes": [],
    }

    tmpdir = tempfile.mkdtemp(prefix="s4e_selftest_")
    dxf_path = os.path.join(tmpdir, "s4e_demo.dxf")

    # 1) build fixture (always) --------------------------------------------
    try:
        fixture_summary = _build_selftest_dxf(dxf_path)
        fixture_summary["path"] = dxf_path
        fixture_summary["bytes"] = os.path.getsize(dxf_path)
        result["fixture"] = fixture_summary
    except Exception as exc:  # ezdxf failure -> record, keep going with wiring
        result["fixture"] = {"error": "%s: %s" % (type(exc).__name__, exc), "path": dxf_path}
        result["notes"].append("fixture build FAILED; detect path unavailable")

    # 2) wiring check on the loader itself ---------------------------------
    mods, missing = require_siblings(SIBLINGS_FOR_DETECT)
    result["siblings_present"] = sorted(mods.keys())
    result["siblings_missing"] = sorted(missing)
    result["wiring"] = {
        "loader": "importlib.util.spec_from_file_location",
        "search_dir": HERE,
        "expected": list(SIBLINGS_FOR_DETECT),
        "callables_checked": {},
    }
    expected_api = {
        "normalize": ["parse_modelspace", "entity_to_segments"],
        "insert_expand": ["expand"],
        "unit_anchor": ["infer_from_dxf"],
        "evidence_grid": ["score"],
    }
    for name, fns in expected_api.items():
        mod = mods.get(name)
        result["wiring"]["callables_checked"][name] = {
            fn: (mod is not None and callable(getattr(mod, fn, None))) for fn in fns
        }

    # 3) eval self-check (pure; always runnable) ---------------------------
    # Synthetic pred with known per-handle evidence + walls, and a truth set,
    # so the eval subcommand's math is exercised with a checkable answer.
    synth_pred = {
        "seg_ir": seg_ir_skeleton("selfcheck"),
        "scores": {
            "per_handle": {
                "A": {"score": 0.9, "evidence": {"parallel": 0.9, "thickness": 0.9, "junction": 0.8, "layer": 1.0}},
                "B": {"score": 0.8, "evidence": {"parallel": 0.7, "thickness": 0.8, "junction": 0.7, "layer": 1.0}},
                "C": {"score": 0.2, "evidence": {"parallel": 0.1, "thickness": 0.2, "junction": 0.1, "layer": 0.0}},
            },
            "walls": [{"handles": ["A", "B"], "axis": [[0, 0], [1, 0]], "thickness": 240.0}],
        },
    }
    synth_truth = {
        "truth": TRUTH_VERSION, "drawing_id": "selfcheck",
        "walls": [{"id": "w1", "axis": [[0, 0], [1, 0]], "thickness": 240.0,
                   "layer": "WALL", "handles": ["A", "B"]}],
        "openings": [], "wall_handles_flat": ["A", "B", "D"],  # D is a missed wall handle
    }
    try:
        result["eval_selfcheck"] = run_eval(synth_pred, synth_truth, threshold=DEFAULT_THRESHOLD)
    except Exception as exc:
        result["eval_selfcheck"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
        result["notes"].append("eval self-check FAILED")

    # 4) full end-to-end IF all siblings present and fixture built ----------
    fixture_ok = isinstance(result["fixture"], dict) and "error" not in result["fixture"]
    if not missing and fixture_ok:
        result["mode"] = "full"
        try:
            pred = run_detect(dxf_path, no_layer_channel=False, mods=mods)
            result["detect"] = {
                "n_segments": len(pred["seg_ir"].get("segments") or []),
                "units": pred["seg_ir"].get("units"),
                "scale_mm_per_unit": pred["seg_ir"].get("scale_mm_per_unit"),
                "n_handles_scored": len((pred["scores"].get("per_handle") or {})),
                "n_walls": len((pred["scores"].get("walls") or [])),
            }
            # truth from the native WALL handles we planted in the fixture
            wall_handles = [
                e["handle"] for e in result["fixture"].get("native_entities", [])
                if e.get("layer") == "WALL"
            ]
            truth = {
                "truth": TRUTH_VERSION, "drawing_id": pred["seg_ir"]["drawing_id"],
                "walls": [{"id": "w1", "axis": [[0, 0], [5000, 0]], "thickness": 240.0,
                           "layer": "WALL", "handles": wall_handles}],
                "openings": [], "wall_handles_flat": wall_handles,
            }
            result["eval"] = run_eval(pred, truth, threshold=DEFAULT_THRESHOLD)
        except Exception as exc:
            result["mode"] = "full_errored"
            result["detect"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
            result["notes"].append("full detect/eval raised; see detect.error")
    else:
        result["mode"] = "wiring_check"
        if missing:
            result["notes"].append("degraded: sibling module(s) absent (parallel build): "
                                   + ", ".join(sorted(missing)))
        if not fixture_ok:
            result["notes"].append("degraded: fixture unavailable")

    # 5) write report ------------------------------------------------------
    os.makedirs(os.path.dirname(out_report_path), exist_ok=True)
    with open(out_report_path, "w", encoding="ascii") as fh:
        json.dump(result, fh, indent=2, sort_keys=False)
        fh.write("\n")

    return result


# --- command handlers -----------------------------------------------------
def cmd_detect(args):
    mods, missing = require_siblings(SIBLINGS_FOR_DETECT)
    if missing:
        return _die_missing(missing)
    if not os.path.exists(args.dxf):
        sys.stderr.write("input DXF not found: %s\n" % args.dxf)
        return 2
    product = run_detect(args.dxf, args.no_layer_channel, mods)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="ascii") as fh:
        json.dump(product, fh, indent=2)
        fh.write("\n")
    sys.stdout.write(
        "detect OK -> %s (segments=%d, walls=%d)\n" % (
            args.out,
            len(product["seg_ir"].get("segments") or []),
            len(product["scores"].get("walls") or []),
        )
    )
    return 0


def cmd_eval(args):
    with open(args.pred, "r", encoding="utf-8") as fh:
        pred = json.load(fh)
    with open(args.truth, "r", encoding="utf-8") as fh:
        truth = json.load(fh)
    report = run_eval(pred, truth, threshold=args.threshold)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="ascii") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    b = report["baseline"]
    sys.stdout.write(
        "eval OK -> %s (P=%.3f R=%.3f F1=%.3f, tp=%d fp=%d fn=%d)\n" % (
            args.out, b["precision"], b["recall"], b["f1"], b["tp"], b["fp"], b["fn"],
        )
    )
    return 0


def cmd_selftest(args):
    out = args.out or os.path.join(HERE, "..", "..", "..", "reports", "e2", "s4", "selftest_demo.json")
    out = os.path.abspath(out)
    result = run_selftest(out)
    # human-readable tail
    sys.stdout.write("=== S4-E SELFTEST ===\n")
    sys.stdout.write("mode: %s\n" % result["mode"])
    fx = result["fixture"] or {}
    if "error" in fx:
        sys.stdout.write("fixture: ERROR %s\n" % fx["error"])
    else:
        sys.stdout.write("fixture: %s (%s bytes, %d native ents, nested INSERT=%s)\n" % (
            os.path.basename(fx.get("path", "?")), fx.get("bytes"),
            len(fx.get("native_entities", [])),
            (fx.get("insert") or {}).get("block"),
        ))
    sys.stdout.write("siblings present: %s\n" % (result["siblings_present"] or "(none)"))
    sys.stdout.write("siblings missing: %s\n" % (result["siblings_missing"] or "(none)"))
    esc = result.get("eval_selfcheck") or {}
    if "error" in esc:
        sys.stdout.write("eval self-check: ERROR %s\n" % esc["error"])
    else:
        b = esc.get("baseline", {})
        sys.stdout.write("eval self-check: P=%.3f R=%.3f F1=%.3f (tp=%d fp=%d fn=%d), ablation rows=%d\n" % (
            b.get("precision", 0), b.get("recall", 0), b.get("f1", 0),
            b.get("tp", 0), b.get("fp", 0), b.get("fn", 0), len(esc.get("ablation", [])),
        ))
    if result.get("detect"):
        d = result["detect"]
        if "error" in d:
            sys.stdout.write("detect (full): ERROR %s\n" % d["error"])
        else:
            sys.stdout.write("detect (full): segments=%d walls=%d handles_scored=%d scale=%s\n" % (
                d.get("n_segments", 0), d.get("n_walls", 0),
                d.get("n_handles_scored", 0), d.get("scale_mm_per_unit"),
            ))
    for n in result.get("notes", []):
        sys.stdout.write("note: %s\n" % n)
    sys.stdout.write("report: %s\n" % out)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="s4e-detect", description="E2/S4 detector CLI + eval harness")
    p.add_argument("--selftest", action="store_true", help="build fixture, run detect+eval or wiring check")
    p.add_argument("--out", help="(selftest) report path override", default=None)
    sub = p.add_subparsers(dest="cmd")

    pd = sub.add_parser("detect", help="DXF -> {seg_ir, scores}")
    pd.add_argument("--dxf", required=True)
    pd.add_argument("--out", required=True)
    pd.add_argument("--no-layer-channel", action="store_true", dest="no_layer_channel")
    pd.set_defaults(func=cmd_detect)

    pe = sub.add_parser("eval", help="pred vs truth -> P/R/F1 + ablation")
    pe.add_argument("--pred", required=True)
    pe.add_argument("--truth", required=True)
    pe.add_argument("--out", required=True)
    pe.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    pe.set_defaults(func=cmd_eval)
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selftest:
        return cmd_selftest(args)
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
