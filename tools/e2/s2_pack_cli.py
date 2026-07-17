#!/usr/bin/env python3
"""s2_pack_cli.py -- E2 S/F/M synthetic wall-drawing pack builder (CARD S2-E).

Builds packs of synthetic 2D floor-plan-ish DXF drawings together with a
machine-readable ground-truth ledger, for training / evaluating a wall
detector. Three tiers of increasing realism:

    S  = grammar only            (clean walls)
    F  = grammar + openings       (walls + door/window spans)
    M  = grammar + openings + noise (level 2-3 distractors / perturbation)

This file OWNS only the deterministic part of the pipeline: turning a
`WallPlan` into a DXF + TRUTH-LEDGER, and writing the pack manifest. The
*content* of a plan comes from sibling "synth" modules that are built in
parallel (they may not exist yet); this CLI imports them by path and
degrades gracefully when one is absent.

------------------------------------------------------------------------
SHARED DATA CONTRACTS  (exact keys -- do not rename)
------------------------------------------------------------------------

WallPlan  (produced by synth/grammar.py, extended by openings.py/noise.py):

    {"plan": "wp.v1", "seed": int, "units": "mm",
     "walls":    [{"id": "w1", "axis": [[x,y],[x,y]],
                   "thickness": 240.0, "layer": "WALL"}],
     "openings": [{"id": "o1", "wall_id": "w1",
                   "span_along_axis": [t0, t1], "type": "door|window"}]}
        span t in 0..1 along the wall axis (A + (B-A)*t).
    Optional extension consumed by the renderer (may be added by noise.py):
     "distractors": [{"type": "line",   "start": [x,y], "end": [x,y], "layer": "NOISE"},
                     {"type": "circle", "center": [x,y], "radius": r,  "layer": "NOISE"}]

TRUTH-LEDGER v1  (emitted per drawing as NNNN.truth.json):

    {"truth": "wall.v1", "drawing_id": "str",
     "walls":    [{"id": "w1", "axis": [[x,y],[x,y]], "thickness": 240.0,
                   "layer": "WALL", "handles": ["h1","h2"]}],
     "openings": [{"id": "o1", "wall_id": "w1",
                   "span_along_axis": [t0,t1], "type": "door|window"}],
     "wall_handles_flat": ["h1","h2"]}

    Each wall is rendered as its two face lines (axis offset by +/-thickness/2)
    on layer WALL; the two DXF entity handles become the wall's `handles`.
    `wall_handles_flat` is those handles in wall order. Openings and noise
    distractors are visual only -- they carry NO truth handles.

------------------------------------------------------------------------
SYNTH MODULE INTERFACE  (expected of the parallel-built sibling modules)
------------------------------------------------------------------------
Resolved by trying the candidate function names below, first callable wins:

    grammar.py : build_plan(seed) -> WallPlan            (also: generate/make_plan/build/plan)
    openings.py: add_openings(plan, seed) -> WallPlan     (also: apply/add/openings/place_openings)
    noise.py   : add_noise(plan, seed, level) -> WallPlan (also: apply/add/noise/apply_noise)

A stage that returns None is treated as an in-place mutation of `plan`.

Exit codes: 0 ok | 2 usage | 3 required synth module absent (named) |
            4 synth module present but interface mismatch | 1 other error.

ezdxf is ALLOWED for this card (synthetic DXF generation; no original CAD
file is read or mutated). DXF version: R2018 (AC1032), ASCII.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import shutil
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

import ezdxf

# --------------------------------------------------------------------------
# Constants / contracts
# --------------------------------------------------------------------------
SYNTH_DIR = Path(__file__).resolve().parent / "synth"
DXF_VERSION = "R2018"                     # -> AC1032, ascii
MANIFEST_SCHEMA = "s2pack.v1"
TRUTH_SCHEMA = "wall.v1"
PLAN_SCHEMA = "wp.v1"
DEFAULT_THICKNESS = 240.0

TIER_MODULES = {
    "S": ["grammar"],
    "F": ["grammar", "openings"],
    "M": ["grammar", "openings", "noise"],
}

FN_CANDIDATES = {
    # canonical S2-card contract names first (plan_random / assign), legacy guesses after
    "grammar": ["plan_random", "build_plan", "generate", "make_plan", "build", "plan"],
    "openings": ["assign", "add_openings", "apply", "add", "openings", "place_openings"],
    "noise": ["add_noise", "apply", "add", "noise", "apply_noise"],
}

# Layer palette (aci colours): WALL=white/black, OPENING=cyan, NOISE=grey
LAYERS = {"WALL": 7, "OPENING": 4, "NOISE": 8}


class MissingModule(Exception):
    """A synth module required by the tier does not exist on disk."""

    def __init__(self, name: str):
        super().__init__(name)
        self.name = name


class InterfaceError(Exception):
    """A synth module exists but does not expose / accept the expected call."""


# --------------------------------------------------------------------------
# Synth module loading (by path -- no package, no __init__.py)
# --------------------------------------------------------------------------
def load_synth_module(name: str):
    """Import synth/<name>.py by path. Return module, or None if file absent."""
    path = SYNTH_DIR / f"{name}.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"_s2e_synth_{name}", str(path))
    if spec is None or spec.loader is None:
        raise InterfaceError(f"{name}.py exists but could not be loaded as a module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # may raise -> surfaced as runtime error
    return module


def resolve_callable(module, candidates):
    """Return the first callable attribute in `candidates`, else raise."""
    for fn_name in candidates:
        fn = getattr(module, fn_name, None)
        if callable(fn):
            return fn
    raise InterfaceError(
        f"module {getattr(module, '__name__', '?')} exposes none of "
        f"the expected callables: {candidates}"
    )


# --------------------------------------------------------------------------
# Stage calls (documented signatures; loud on mismatch)
# --------------------------------------------------------------------------
def _stage_result(returned, plan):
    """Stage may return a new plan dict, or None to signal in-place mutation."""
    if returned is None:
        return plan
    if isinstance(returned, dict):
        return returned
    raise InterfaceError(f"stage returned {type(returned).__name__}, expected dict or None")


def call_grammar(fn, seed):
    try:
        plan = fn(seed)
    except TypeError as exc:
        raise InterfaceError(f"grammar.{fn.__name__}(seed) call failed: {exc}") from exc
    if not isinstance(plan, dict):
        raise InterfaceError(f"grammar.{fn.__name__} returned {type(plan).__name__}, expected WallPlan dict")
    return plan


def call_openings(fn, plan, seed):
    try:
        return _stage_result(fn(plan, seed), plan)
    except TypeError as exc:
        raise InterfaceError(f"openings.{fn.__name__}(plan, seed) call failed: {exc}") from exc


def call_noise(fn, plan, seed, level):
    try:
        return _stage_result(fn(plan, seed, level), plan)
    except TypeError as exc:
        raise InterfaceError(f"noise.{fn.__name__}(plan, seed, level) call failed: {exc}") from exc


# --------------------------------------------------------------------------
# Plan validation
# --------------------------------------------------------------------------
def assert_wallplan(plan):
    if not isinstance(plan, dict):
        raise InterfaceError("plan is not a dict")
    if plan.get("plan") != PLAN_SCHEMA:
        raise InterfaceError(f"plan schema tag != {PLAN_SCHEMA!r} (got {plan.get('plan')!r})")
    if not isinstance(plan.get("walls"), list):
        raise InterfaceError("plan.walls missing or not a list")
    for w in plan["walls"]:
        axis = w.get("axis")
        if (not isinstance(axis, (list, tuple)) or len(axis) != 2
                or any(len(p) != 2 for p in axis)):
            raise InterfaceError(f"wall {w.get('id')!r} has malformed axis: {axis!r}")


# --------------------------------------------------------------------------
# Rendering: WallPlan -> (ezdxf doc, TRUTH-LEDGER dict)
# --------------------------------------------------------------------------
def _ensure_layers(doc):
    for name, color in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)


def _draw_wall(msp, axis, thickness, layer):
    """Draw a wall as its two parallel face lines. Return [h1, h2]."""
    (ax, ay), (bx, by) = axis[0], axis[1]
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length == 0.0:            # degenerate wall: faces coincide with the point
        nx, ny = 0.0, 0.0
    else:
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux        # unit normal
    off = thickness / 2.0
    f1 = msp.add_line((ax + nx * off, ay + ny * off),
                      (bx + nx * off, by + ny * off), dxfattribs={"layer": layer})
    f2 = msp.add_line((ax - nx * off, ay - ny * off),
                      (bx - nx * off, by - ny * off), dxfattribs={"layer": layer})
    return [f1.dxf.handle, f2.dxf.handle]


def _draw_opening_marker(msp, wall_axis, thickness, span):
    """Perpendicular tick at the span midpoint (visual only, no truth handle)."""
    (ax, ay), (bx, by) = wall_axis[0], wall_axis[1]
    t0, t1 = span
    tmid = (float(t0) + float(t1)) / 2.0
    cx, cy = ax + (bx - ax) * tmid, ay + (by - ay) * tmid
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    off = max(thickness, DEFAULT_THICKNESS)
    msp.add_line((cx - nx * off, cy - ny * off),
                 (cx + nx * off, cy + ny * off), dxfattribs={"layer": "OPENING"})


def _draw_distractor(msp, d):
    """Render a noise entity on its layer (visual only, no truth handle)."""
    layer = d.get("layer", "NOISE")
    dtype = d.get("type", "line")
    if dtype == "line":
        msp.add_line(tuple(d["start"]), tuple(d["end"]), dxfattribs={"layer": layer})
    elif dtype == "circle":
        msp.add_circle(tuple(d["center"]), float(d["radius"]), dxfattribs={"layer": layer})
    # unknown distractor types are silently skipped -- renderer stays robust


def render_plan(plan, drawing_id):
    """Return (ezdxf doc, TRUTH-LEDGER v1 dict) for a WallPlan."""
    doc = ezdxf.new(DXF_VERSION)
    doc.header["$INSUNITS"] = 4  # plans are authored in millimetres; say so honestly
    _ensure_layers(doc)
    msp = doc.modelspace()

    walls_truth = []
    flat_handles = []
    axis_by_wall = {}
    thick_by_wall = {}
    for w in plan.get("walls", []):
        axis = [list(w["axis"][0]), list(w["axis"][1])]
        thickness = float(w.get("thickness", DEFAULT_THICKNESS))
        layer = w.get("layer", "WALL")
        handles = _draw_wall(msp, axis, thickness, layer)
        walls_truth.append({
            "id": w["id"], "axis": axis, "thickness": thickness,
            "layer": layer, "handles": handles,
        })
        flat_handles.extend(handles)
        axis_by_wall[w["id"]] = axis
        thick_by_wall[w["id"]] = thickness

    openings_truth = []
    for o in plan.get("openings", []):
        openings_truth.append({
            "id": o["id"], "wall_id": o["wall_id"],
            "span_along_axis": [float(o["span_along_axis"][0]), float(o["span_along_axis"][1])],
            "type": o["type"],
        })
        if o["wall_id"] in axis_by_wall:
            _draw_opening_marker(msp, axis_by_wall[o["wall_id"]],
                                 thick_by_wall[o["wall_id"]], o["span_along_axis"])

    for d in plan.get("distractors", []):
        _draw_distractor(msp, d)

    truth = {
        "truth": TRUTH_SCHEMA,
        "drawing_id": drawing_id,
        "walls": walls_truth,
        "openings": openings_truth,
        "wall_handles_flat": flat_handles,
    }
    return doc, truth


# --------------------------------------------------------------------------
# Plan generation (uses synth modules) & pack writing
# --------------------------------------------------------------------------
def generate_plans(tier, seeds, noise_level):
    """Build one WallPlan per seed via the synth modules for `tier`.

    Raises MissingModule(name) if a required module is absent (parallel build).
    Returns (plans, modules_meta).
    """
    required = TIER_MODULES[tier]
    resolved = {}
    meta = {}
    post_emit = None
    for name in required:
        module = load_synth_module(name)
        if module is None:
            raise MissingModule(name)
        if name == "noise" and not any(callable(getattr(module, c, None)) for c in FN_CANDIDATES["noise"]):
            # S2-D card contract: noise is DXF-level messify(dxf_in, dxf_out, seed, level, ledger)
            # -> applied post-emit in write_pack, not as a plan stage.
            fn = getattr(module, "messify", None)
            if not callable(fn):
                raise InterfaceError("noise.py exposes neither a plan-stage callable nor messify()")
            post_emit = fn
            meta[name] = {"path": str(SYNTH_DIR / f"{name}.py"), "fn": "messify(post-emit)"}
            continue
        fn = resolve_callable(module, FN_CANDIDATES[name])
        resolved[name] = fn
        meta[name] = {"path": str(SYNTH_DIR / f"{name}.py"), "fn": fn.__name__}

    plans = []
    for s in seeds:
        plan = call_grammar(resolved["grammar"], s)
        assert_wallplan(plan)
        if "openings" in resolved:
            plan = call_openings(resolved["openings"], plan, s)
        if "noise" in resolved:
            plan = call_noise(resolved["noise"], plan, s, noise_level)
        plans.append(plan)
    return plans, meta, post_emit


def write_pack(outdir, tier, base_seed, plans, seeds, noise_level, modules_meta, post_emit=None):
    """Render each plan and write NNNN.dxf + NNNN.truth.json + manifest.json."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    files = []
    for i, (plan, seed) in enumerate(zip(plans, seeds)):
        drawing_id = f"{i:04d}"
        doc, truth = render_plan(plan, drawing_id)
        dxf_name = f"{drawing_id}.dxf"
        truth_name = f"{drawing_id}.truth.json"
        doc.saveas(outdir / dxf_name)   # ascii DXF
        if post_emit is not None:
            raw = outdir / f"{drawing_id}.raw.dxf"
            (outdir / dxf_name).replace(raw)
            truth, _handle_map = post_emit(str(raw), str(outdir / dxf_name), seed, noise_level, truth)
            raw.unlink()
        _write_json(outdir / truth_name, truth)
        files.append({
            "drawing_id": drawing_id, "dxf": dxf_name,
            "truth": truth_name, "seed": seed,
        })

    manifest = {
        "manifest": MANIFEST_SCHEMA,
        "tier": tier,
        "n": len(plans),
        "seed": base_seed,
        "seeds": seeds,
        "noise_level": noise_level if tier == "M" else None,
        "dxf_version": DXF_VERSION,
        "truth_schema": TRUTH_SCHEMA,
        "modules": modules_meta,
        "files": files,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(outdir / "manifest.json", manifest)
    return manifest


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# --------------------------------------------------------------------------
# Schema validators (used by selftest / manifest-schema check)
# --------------------------------------------------------------------------
def validate_manifest(m):
    errs = []
    if m.get("manifest") != MANIFEST_SCHEMA:
        errs.append(f"manifest tag != {MANIFEST_SCHEMA!r}")
    for key in ("tier", "n", "seed", "seeds", "files", "dxf_version"):
        if key not in m:
            errs.append(f"missing key: {key}")
    if m.get("tier") not in TIER_MODULES:
        errs.append(f"bad tier: {m.get('tier')!r}")
    if not isinstance(m.get("seeds"), list):
        errs.append("seeds not a list")
    if not isinstance(m.get("files"), list):
        errs.append("files not a list")
    else:
        if isinstance(m.get("n"), int) and len(m["files"]) != m["n"]:
            errs.append(f"n={m.get('n')} but {len(m['files'])} file entries")
        for i, f in enumerate(m["files"]):
            for key in ("drawing_id", "dxf", "truth", "seed"):
                if key not in f:
                    errs.append(f"files[{i}] missing key: {key}")
    return errs


def validate_truth(t):
    errs = []
    if t.get("truth") != TRUTH_SCHEMA:
        errs.append(f"truth tag != {TRUTH_SCHEMA!r}")
    for key in ("drawing_id", "walls", "openings", "wall_handles_flat"):
        if key not in t:
            errs.append(f"missing key: {key}")
    flat = []
    for i, w in enumerate(t.get("walls", [])):
        for key in ("id", "axis", "thickness", "layer", "handles"):
            if key not in w:
                errs.append(f"walls[{i}] missing key: {key}")
        flat.extend(w.get("handles", []))
    for i, o in enumerate(t.get("openings", [])):
        for key in ("id", "wall_id", "span_along_axis", "type"):
            if key not in o:
                errs.append(f"openings[{i}] missing key: {key}")
    if flat != t.get("wall_handles_flat", flat):
        errs.append("wall_handles_flat != flattened wall handles")
    return errs


# --------------------------------------------------------------------------
# Built-in reference plan (for degraded selftest, when grammar.py is absent)
# --------------------------------------------------------------------------
def reference_plan(seed, jitter):
    """A tiny deterministic U-shaped 3-wall plan; `jitter` varies drawings."""
    j = float(jitter)
    return {
        "plan": PLAN_SCHEMA, "seed": seed, "units": "mm",
        "walls": [
            {"id": "w1", "axis": [[0.0 + j, 0.0], [4000.0 + j, 0.0]],
             "thickness": 240.0, "layer": "WALL"},
            {"id": "w2", "axis": [[4000.0 + j, 0.0], [4000.0 + j, 3000.0]],
             "thickness": 240.0, "layer": "WALL"},
            {"id": "w3", "axis": [[4000.0 + j, 3000.0], [0.0 + j, 3000.0]],
             "thickness": 200.0, "layer": "WALL"},
        ],
        "openings": [],
    }


# --------------------------------------------------------------------------
# Selftest
# --------------------------------------------------------------------------
def _validate_pack_on_disk(outdir, log):
    """Read pack back from disk and validate manifest + each drawing. Return ok."""
    ok = True
    manifest_path = Path(outdir) / "manifest.json"
    if not manifest_path.is_file():
        log("  FAIL manifest.json not written")
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    m_errs = validate_manifest(manifest)
    if m_errs:
        ok = False
        log(f"  FAIL manifest schema: {m_errs}")
    else:
        log(f"  ok   manifest.json schema-valid (tier={manifest['tier']}, n={manifest['n']})")

    for f in manifest.get("files", []):
        dxf_path = Path(outdir) / f["dxf"]
        truth_path = Path(outdir) / f["truth"]
        # DXF: exists, non-empty, ascii, readable, has WALL entities
        if not dxf_path.is_file() or dxf_path.stat().st_size == 0:
            ok = False
            log(f"  FAIL {f['dxf']} missing/empty")
            continue
        head = dxf_path.read_bytes()[:8]
        is_ascii = head.lstrip().startswith(b"0")
        try:
            rdoc = ezdxf.readfile(str(dxf_path))
            entity_handles = {e.dxf.handle for e in rdoc.modelspace()}
            wall_ents = sum(1 for e in rdoc.modelspace() if e.dxf.layer == "WALL")
        except Exception as exc:  # noqa: BLE001
            ok = False
            log(f"  FAIL {f['dxf']} not re-readable by ezdxf: {exc}")
            continue
        # TRUTH: valid schema, handles present in the DXF
        if not truth_path.is_file():
            ok = False
            log(f"  FAIL {f['truth']} missing")
            continue
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        t_errs = validate_truth(truth)
        missing_h = [h for h in truth.get("wall_handles_flat", []) if h not in entity_handles]
        if t_errs or missing_h or wall_ents == 0 or not is_ascii:
            ok = False
            log(f"  FAIL {f['dxf']}/{f['truth']}: schema={t_errs} "
                f"missing_handles={missing_h} wall_ents={wall_ents} ascii={is_ascii}")
        else:
            log(f"  ok   {f['dxf']} (ascii, {wall_ents} WALL ents) + "
                f"{f['truth']} ({len(truth['walls'])} walls, "
                f"handles cross-check OK)")
    return ok


def selftest():
    lines = []

    def log(msg):
        lines.append(msg)
        print(msg, flush=True)

    tmp = Path(tempfile.mkdtemp(prefix="s2e_selftest_"))
    grammar_present = (SYNTH_DIR / "grammar.py").is_file()
    log("=== s2_pack_cli selftest ===")
    log(f"python      : {sys.version.split()[0]}")
    log(f"ezdxf       : {ezdxf.__version__}")
    log(f"synth dir   : {SYNTH_DIR}  (exists={SYNTH_DIR.is_dir()})")
    log(f"grammar.py  : {'present' if grammar_present else 'ABSENT (parallel build)'}")
    log(f"temp pack   : {tmp}")

    verdict = "PASS"
    try:
        if grammar_present:
            log("mode        : module-driven -- building real 2-drawing S pack")
            seeds = [1234, 1235]
            plans, meta, post_emit = generate_plans("S", seeds, noise_level=2)
            write_pack(tmp, "S", 1234, plans, seeds, 2, meta, post_emit)
        else:
            log("mode        : DEGRADED -- grammar.py absent; manifest-schema check "
                "via built-in reference plan (same render+manifest code path)")
            seeds = [1234, 1235]
            plans = [reference_plan(s, jitter=i * 100) for i, s in enumerate(seeds)]
            meta = {"grammar": {"path": None, "fn": "<built-in reference_plan fixture>"}}
            write_pack(tmp, "S", 1234, plans, seeds, 2, meta)
            verdict = "PARTIAL_PASS"

        log("validating pack on disk:")
        ok = _validate_pack_on_disk(tmp, log)
        if not ok:
            verdict = "BLOCKED"
    except Exception as exc:  # noqa: BLE001
        verdict = "BLOCKED"
        log(f"  EXCEPTION during selftest: {exc}")
        log(traceback.format_exc())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        log(f"cleaned temp pack: {tmp}")

    log(f"VERDICT: {verdict}")
    if verdict == "PARTIAL_PASS":
        log("  note: grammar->plan integration NOT exercised (module absent). "
            "Render + TRUTH-LEDGER + manifest pipeline validated end-to-end via reference plan.")
    return 0 if verdict in ("PASS", "PARTIAL_PASS") else 1


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def cmd_build(args):
    tier = args.tier
    noise_level = args.noise_level
    if tier == "M" and noise_level not in (2, 3):
        print(f"[s2_pack_cli] tier M requires --noise-level 2 or 3 (got {noise_level})",
              file=sys.stderr)
        return 2
    seeds = [args.seed + i for i in range(args.n)]
    try:
        plans, meta, post_emit = generate_plans(tier, seeds, noise_level)
    except MissingModule as mm:
        print(f"[s2_pack_cli] required synth module absent for tier {tier}: "
              f"{mm.name}.py (expected at {SYNTH_DIR / (mm.name + '.py')}). "
              f"Parallel build not complete -- retry once {mm.name}.py lands.",
              file=sys.stderr)
        return 3
    except InterfaceError as ie:
        print(f"[s2_pack_cli] synth interface error: {ie}", file=sys.stderr)
        return 4
    manifest = write_pack(args.out, tier, args.seed, plans, seeds, noise_level, meta, post_emit)
    print(f"[s2_pack_cli] built tier={tier} n={manifest['n']} seed={args.seed} "
          f"-> {Path(args.out).resolve()}")
    print(f"[s2_pack_cli] files: manifest.json + "
          f"{manifest['n']}x(NNNN.dxf + NNNN.truth.json)")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="s2_pack_cli",
        description="E2 S/F/M synthetic wall-drawing pack builder.")
    p.add_argument("--selftest", action="store_true",
                   help="run self-contained selftest (builds to OS temp) and exit")
    sub = p.add_subparsers(dest="cmd")
    b = sub.add_parser("build", help="build a pack")
    b.add_argument("--tier", required=True, choices=["S", "F", "M"])
    b.add_argument("--n", type=int, required=True, help="number of drawings")
    b.add_argument("--seed", type=int, required=True, help="base seed (drawing i -> seed+i)")
    b.add_argument("--out", required=True, help="output pack directory")
    b.add_argument("--noise-level", type=int, default=2, choices=[2, 3],
                   dest="noise_level", help="M-tier noise level (2-3)")
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # --selftest handled before subcommand dispatch so it works standalone.
    if "--selftest" in argv:
        return selftest()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "build":
        return cmd_build(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
