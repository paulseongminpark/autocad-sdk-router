#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""asm_probe_driver.py -- WaveS0 ASM/solids headless reachability probe.

PROBE-ONLY, not merged, not wired into tools/patch_ops (that split registry has
no entries for write.entity.{region,body,solid3d.*,surface,nurbsurface} yet --
that is the S-wave's job). This script drives those 9 native op_ids DIRECTLY
against the same run_job.run_router_cad_job / ir_builder / cad_diff plumbing
patch_engine.apply_staged uses internally, building the native job doc itself
(op_roundtrip_probe.py's resolve_native_op would return None for all 9 today --
NATIVE_WRITE_OP_MAP has no entries for this family, confirmed by inspection).

No C++ edits. Uses the worktree's existing prebuilt/2027 native modules as-is
(verified via string search that all 9 target op_ids + 3 AcBr op_ids ARE
present as literal byte strings in Ariadne.AcadNative.crx/.arx -- no rebuild
required to test the CURRENT dispatcher).

For each write op:
  1. sha256 the tracked fixture (tests/fixtures/native_sample.dwg) -- BEFORE.
  2. stage a fresh copy into runs/waveS0_asmprobe/<tag>/staged_input.dwg.
  3. pre-inspect (inspect.database.graph, write_mode=read) -> IR.
  4. apply the write op (write_mode=write_copy) with a hand-authored job doc
     (ariadne.autocad_sdk_job.v2 shape, mirrors patch_engine._native_job_doc).
  5. sha256 the tracked fixture again -- AFTER (must be unchanged, every time).
  6. post-inspect the mutated staged_output.dwg -> IR.
  7. cad_diff.compute_diff(pre_ir, post_ir) -> added/removed/modified handles.
  8. classify: CREATED_REAL / CREATED_DEGENERATE / ENGINE_MISSING / HANDLER_BUG
     (non-degeneracy confirmed via a THIRD pass: AcBr read ops --
     inspect.brep.from_entity/validate/bounds, compute.brep.volume/
     surface_area/massprops -- run against the new entity's handle on
     staged_output.dwg, write_mode=read).

write.entity.region needs a pre-existing curve: a closed write.entity.polyline
(already a PROVEN native op, in patch_ops today) is created first on the SAME
staged file, chained the way patch_engine chains multi-op patches
(current_input = previous step's staged_output), then region consumes its
returned handle.

Run: python tools/asm_probe_driver.py [--only op_id[,op_id...]]
Writes one JSON summary to runs/waveS0_asmprobe/summary.json and prints a
compact table to stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from typing import Any, Dict, List, Optional

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROUTER_HOME = os.path.dirname(THIS_DIR)
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import run_job          # noqa: E402  (sibling, ROUTER_HOME derived from THIS file's path)
import ir_builder        # noqa: E402
import cad_diff          # noqa: E402

FIXTURE = os.path.join(ROUTER_HOME, "tests", "fixtures", "native_sample.dwg")
RUNS_ROOT = os.path.join(ROUTER_HOME, "runs", "waveS0_asmprobe")

BREP_READ_OPS = [
    "inspect.brep.from_entity",
    "inspect.brep.validate",
    "inspect.brep.bounds",
    "compute.brep.volume",
    "compute.brep.surface_area",
    "compute.brep.massprops",
]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def native_job_doc(operation: str, args: Dict[str, Any], write_mode: str) -> Dict[str, Any]:
    return {
        "schema": "ariadne.autocad_sdk_job.v2",
        "operation": operation,
        "write_mode": write_mode,
        "policy": {"write_mode": write_mode, "require_staged_copy": True,
                   "save": write_mode != "read", "lock_document": True},
        "source_agent": "s0-asmprobe",
        "args": args,
    }


def write_job(path: str, doc: Dict[str, Any]) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
    return path


def run_graph(dwg_path: str, run_dir: str) -> Dict[str, Any]:
    return run_job.run_router_cad_job(dwg_path, run_dir, "inspect.database.graph", write_mode="read")


def build_ir(result_obj: Dict[str, Any], dwg_path: str, phase: str, run_dir: str):
    source_meta = {
        "dwg_path": dwg_path, "original_path": FIXTURE,
        "dwg_name": os.path.basename(FIXTURE), "format": "dwg",
        "byte_size": os.path.getsize(dwg_path), "sha256": sha256_file(dwg_path),
        "extractor": "native_objectarx", "engine_tier": "native_arx",
        "route": "dwg_truth_autocad", "extracted_at": _now_iso(), "phase": phase,
    }
    ir = ir_builder.build_ir_from_database_graph(result_obj, source_meta)
    ir_path = os.path.join(run_dir, "dwg_graph_ir_%s.json" % phase)
    ir_builder.write_ir(ir, ir_path)
    return ir, ir_path


def run_native_write(input_dwg: str, op_id: str, args: Dict[str, Any], run_dir: str) -> Dict[str, Any]:
    """Apply ONE native write op to input_dwg (write_copy). Returns a dict with
    exit_code/error/result/staged_used/staged_output (staged_output only set on
    success)."""
    os.makedirs(run_dir, exist_ok=True)
    job_doc = native_job_doc(op_id, args, "write_copy")
    job_path = write_job(os.path.join(run_dir, "cad_job.json"), job_doc)
    res = run_job.run_router_cad_job(input_dwg, run_dir, op_id, write_mode="write_copy", job_path=job_path)
    mutated = res.get("staged_used")
    if mutated and os.path.isfile(mutated):
        staged_output = os.path.join(run_dir, "staged_output.dwg")
        shutil.copy2(mutated, staged_output)
        res["staged_output"] = staged_output
    else:
        res["staged_output"] = None
    return res


def run_brep_read(dwg_path: str, op_id: str, handle: str, run_dir: str) -> Dict[str, Any]:
    # each brep op gets its OWN subdir -- run_router_cad_job hardcodes
    # stdout.txt/stderr.txt at run_dir root, so sharing one dir across the 6
    # brep ops silently overwrote all but the last op's raw output (found
    # when the first full sweep was killed at the 10-minute cap and left no
    # per-case evidence to reconstruct from disk for the completed cases).
    op_dir = os.path.join(run_dir, op_id.replace(".", "_"))
    job_doc = native_job_doc(op_id, {"handle": handle}, "read")
    job_path = write_job(os.path.join(op_dir, "cad_job.json"), job_doc)
    return run_job.run_router_cad_job(dwg_path, op_dir, op_id, write_mode="read", job_path=job_path)


def probe_one(op_id: str, tag: str, args: Dict[str, Any],
              precreate_curve: bool = False, resume: bool = True) -> Dict[str, Any]:
    """Wrapper: resume from run_dir/case_result.json if present (so a killed
    sweep -- e.g. the 10-minute Bash cap -- doesn't force re-running the
    (expensive) accoreconsole work for cases that already finished), else run
    _probe_one_inner and persist the result to disk IMMEDIATELY (disk-first:
    the in-memory aggregate summary.json is only written at the very end of
    main(), which is exactly what a kill signal destroys)."""
    run_dir = os.path.join(RUNS_ROOT, tag)
    result_path = os.path.join(run_dir, "case_result.json")
    if resume and os.path.isfile(result_path):
        try:
            with open(result_path, "r", encoding="utf-8") as fh:
                cached = json.load(fh)
            if cached.get("classification") not in (None, "DRIVER_EXCEPTION"):
                print("  (resumed from disk: %s)" % result_path)
                return cached
        except (OSError, ValueError):
            pass
    out = _probe_one_inner(op_id, tag, args, precreate_curve=precreate_curve)
    os.makedirs(run_dir, exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    return out


def _probe_one_inner(op_id: str, tag: str, args: Dict[str, Any],
                     precreate_curve: bool = False) -> Dict[str, Any]:
    run_dir = os.path.join(RUNS_ROOT, tag)
    if os.path.isdir(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir, exist_ok=True)

    original_sha_before = sha256_file(FIXTURE)
    staged_input = os.path.join(run_dir, "staged_input.dwg")
    shutil.copy2(FIXTURE, staged_input)

    out: Dict[str, Any] = {"op": op_id, "tag": tag, "args": args, "run_dir": run_dir}

    # pre-inspect
    pre_dir = os.path.join(run_dir, "pre")
    pre_run = run_graph(staged_input, pre_dir)
    if not isinstance(pre_run.get("result"), dict):
        out["classification"] = "PROBE_ERROR"
        out["reason"] = "pre-inspect produced no result (exit=%r err=%r)" % (
            pre_run.get("exit_code"), pre_run.get("error"))
        return out
    pre_ir, pre_ir_path = build_ir(pre_run["result"], staged_input, "pre", run_dir)

    current_input = staged_input
    curve_handle = None
    if precreate_curve:
        # Closed 4-vertex rectangle polyline -- write.entity.polyline is a
        # PROVEN op (already in patch_ops.entities.WRITE_OP_MAP); we call it
        # directly here (bypassing patch_ops) purely to stay self-contained.
        poly_dir = os.path.join(run_dir, "precreate_polyline")
        poly_args = {"points": [{"x": 0.0, "y": 0.0, "bulge": 0.0},
                                 {"x": 30.0, "y": 0.0, "bulge": 0.0},
                                 {"x": 30.0, "y": 20.0, "bulge": 0.0},
                                 {"x": 0.0, "y": 20.0, "bulge": 0.0}],
                     "closed": 1, "layer": "ARIADNE_ASM_PROBE"}
        poly_res = run_native_write(current_input, "write.entity.polyline", poly_args, poly_dir)
        out["precreate_polyline_result"] = {
            "exit_code": poly_res.get("exit_code"), "error": poly_res.get("error"),
            "result": poly_res.get("result"),
        }
        if not poly_res.get("staged_output"):
            out["classification"] = "PROBE_ERROR"
            out["reason"] = "precreate polyline failed, cannot test write.entity.region"
            return out
        result_obj = poly_res.get("result") or {}
        curve_handle = result_obj.get("handle")
        if not curve_handle:
            out["classification"] = "PROBE_ERROR"
            out["reason"] = "precreate polyline returned no handle"
            return out
        current_input = poly_res["staged_output"]
        args = dict(args)
        args["curves"] = [curve_handle]
        out["args"] = args
        out["precreated_curve_handle"] = curve_handle

    # apply the target write op
    apply_dir = os.path.join(run_dir, "apply")
    apply_res = run_native_write(current_input, op_id, args, apply_dir)
    out["exit_code"] = apply_res.get("exit_code")
    out["native_error"] = apply_res.get("error")
    out["native_result"] = apply_res.get("result")

    original_sha_after = sha256_file(FIXTURE)
    out["original_unchanged"] = (original_sha_after == original_sha_before)
    out["original_sha_before"] = original_sha_before
    out["original_sha_after"] = original_sha_after
    if not out["original_unchanged"]:
        out["classification"] = "CRITICAL_ORIGINAL_MUTATED"
        return out

    staged_output = apply_res.get("staged_output")
    if not staged_output:
        out["classification"] = "ENGINE_MISSING_OR_ERROR"
        out["reason"] = apply_res.get("error") or "no mutated staged copy returned"
        return out

    # post-inspect
    post_dir = os.path.join(run_dir, "post")
    post_run = run_graph(staged_output, post_dir)
    if not isinstance(post_run.get("result"), dict):
        out["classification"] = "PROBE_ERROR"
        out["reason"] = "post-inspect produced no result"
        return out
    post_ir, post_ir_path = build_ir(post_run["result"], staged_output, "post", run_dir)

    diff = cad_diff.compute_diff(pre_ir, post_ir)
    added = [r for r in diff["changed_handles"] if r["change"] == "added"]
    # write.entity.region's precreated source curve is ALSO in `added` (the
    # pre_ir baseline predates the precreate step too) -- exclude it so the
    # target-op entity (not the curve that fed it) is the one classified.
    if precreate_curve and curve_handle:
        added = [r for r in added if r["handle"] != curve_handle]
    out["diff_summary"] = diff.get("summary")
    out["added_count"] = len(added)
    out["added_records"] = added

    result_obj = apply_res.get("result") or {}
    native_created = bool(result_obj.get("created"))
    out["native_created_flag"] = native_created
    out["native_errorstatus"] = result_obj.get("errorstatus")

    if not native_created or not added:
        out["classification"] = "CREATE_FAILED_OR_NOOP"
        return out

    # resolve the new entity's bare extracted record (handle/dxf_name/layer --
    # confirms what collectEntitiesFromBlock actually emits for this class)
    new_handle = added[0]["handle"]
    post_entities = {e.get("handle"): e for e in (post_ir.get("entities") or [])}
    new_record = post_entities.get(new_handle) or {}
    out["new_handle"] = new_handle
    out["new_entity_record"] = new_record

    # non-degeneracy pass: AcBr reads against the new handle
    brep_dir = os.path.join(run_dir, "brep")
    brep_results = {}
    for brep_op in BREP_READ_OPS:
        r = run_brep_read(staged_output, brep_op, new_handle, brep_dir)
        brep_results[brep_op] = {
            "exit_code": r.get("exit_code"), "error": r.get("error"), "result": r.get("result"),
        }
    out["brep_results"] = brep_results

    bind_ok = bool((brep_results.get("inspect.brep.from_entity", {}).get("result") or {}).get("bound"))
    volume = (brep_results.get("compute.brep.volume", {}).get("result") or {}).get("volume")
    area = (brep_results.get("compute.brep.surface_area", {}).get("result") or {}).get("surface_area")

    out["brep_bind_ok"] = bind_ok
    out["volume"] = volume
    out["area"] = area

    if bind_ok and ((isinstance(volume, (int, float)) and volume > 1e-9) or
                     (isinstance(area, (int, float)) and area > 1e-9)):
        out["classification"] = "CREATED_REAL"
    elif bind_ok:
        out["classification"] = "CREATED_DEGENERATE"
    else:
        out["classification"] = "CREATED_BUT_BREP_BIND_FAILED"
    return out


CASES = [
    ("write.entity.solid3d.primitive", "solid3d_primitive_box",
     {"primitive": "box", "x": 10.0, "y": 20.0, "z": 30.0, "layer": "ARIADNE_ASM_PROBE"}, False),
    ("write.entity.solid3d.primitive", "solid3d_primitive_sphere",
     {"primitive": "sphere", "radius": 25.0, "layer": "ARIADNE_ASM_PROBE"}, False),
    ("write.entity.solid3d.primitive", "solid3d_primitive_torus",
     {"primitive": "torus", "radius": 25.0, "minor_radius": 5.0, "layer": "ARIADNE_ASM_PROBE"}, False),
    ("write.entity.solid3d.primitive", "solid3d_primitive_wedge",
     {"primitive": "wedge", "x": 10.0, "y": 20.0, "z": 30.0, "layer": "ARIADNE_ASM_PROBE"}, False),
    ("write.entity.solid3d.primitive", "solid3d_primitive_pyramid",
     {"primitive": "pyramid", "height": 30.0, "radius": 15.0, "top_radius": 0.0, "layer": "ARIADNE_ASM_PROBE"}, False),
    ("write.entity.solid3d.primitive", "solid3d_primitive_frustum",
     {"primitive": "frustum", "height": 20.0, "radius": 15.0, "top_radius": 7.0, "layer": "ARIADNE_ASM_PROBE"}, False),
    ("write.entity.solid3d.extrude", "solid3d_extrude",
     {"width": 40.0, "depth": 30.0, "height": 50.0, "layer": "ARIADNE_ASM_PROBE"}, False),
    ("write.entity.solid3d.revolve", "solid3d_revolve",
     {"width": 8.0, "height": 15.0, "angle": 4.71238898038469, "layer": "ARIADNE_ASM_PROBE"}, False),  # 270 deg
    ("write.entity.solid3d.sweep", "solid3d_sweep",
     {"width": 5.0, "height": 3.0, "length": 40.0, "layer": "ARIADNE_ASM_PROBE"}, False),
    ("write.entity.solid3d.loft", "solid3d_loft",
     {"width": 40.0, "depth": 30.0, "top_width": 15.0, "top_depth": 10.0, "height": 60.0, "layer": "ARIADNE_ASM_PROBE"}, False),
    ("write.entity.region", "region_from_polyline",
     {"layer": "ARIADNE_ASM_PROBE"}, True),
    ("write.entity.surface", "surface_from_profile",
     {"width": 25.0, "height": 18.0, "layer": "ARIADNE_ASM_PROBE"}, False),
    ("write.entity.nurbsurface", "nurbsurface_hardcoded",
     {"layer": "ARIADNE_ASM_PROBE"}, False),  # handler reads NO args -- always the same 1x1 patch
    ("write.entity.body", "body_empty",
     {"layer": "ARIADNE_ASM_PROBE"}, False),  # handler builds an empty AcDbBody -- no content setter called
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated tag substrings to filter")
    ap.add_argument("--force", action="store_true", help="ignore any cached case_result.json, re-run live")
    ns = ap.parse_args(argv)

    if not os.path.isfile(FIXTURE):
        print("FIXTURE MISSING: %s" % FIXTURE, file=sys.stderr)
        return 2

    fixture_sha_start = sha256_file(FIXTURE)
    cases = CASES
    if ns.only:
        substrs = ns.only.split(",")
        cases = [c for c in CASES if any(s in c[1] for s in substrs)]

    results: List[Dict[str, Any]] = []
    for op_id, tag, args, precreate in cases:
        print("=== %s (%s) ===" % (tag, op_id))
        try:
            res = probe_one(op_id, tag, args, precreate_curve=precreate, resume=not ns.force)
        except Exception as exc:  # never let one op's crash kill the sweep
            res = {"op": op_id, "tag": tag, "classification": "DRIVER_EXCEPTION",
                   "reason": "%s: %s" % (type(exc).__name__, exc)}
        results.append(res)
        print("  classification=%s" % res.get("classification"))
        if res.get("reason"):
            print("  reason=%s" % res.get("reason"))
        if res.get("volume") is not None or res.get("area") is not None:
            print("  volume=%r area=%r" % (res.get("volume"), res.get("area")))

    fixture_sha_end = sha256_file(FIXTURE)
    summary = {
        "schema": "s0_asmprobe.summary.v1",
        "generated_at": _now_iso(),
        "fixture": FIXTURE,
        "fixture_sha256_start": fixture_sha_start,
        "fixture_sha256_end": fixture_sha_end,
        "fixture_unchanged_overall": fixture_sha_start == fixture_sha_end,
        "results": results,
    }
    os.makedirs(RUNS_ROOT, exist_ok=True)
    summary_path = os.path.join(RUNS_ROOT, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print("\nSummary written to %s" % summary_path)
    print("fixture_unchanged_overall=%s" % summary["fixture_unchanged_overall"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
