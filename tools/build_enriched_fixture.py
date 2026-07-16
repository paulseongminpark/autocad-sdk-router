#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_enriched_fixture.py -- P3b tail: build the enriched probe fixture DWG.

WHY (SDK certification ledger P3b tail / RESULTS 20260714 §5):
  140 REACHABLE ops are "dispatch + arg-validation proven, needs-state
  documented" -- the state they need (3DSOLIDs, xdata, an extension dict, a
  saved layerstate, an assoc action, known-geometry curves) does NOT exist in
  tests/fixtures/native_sample.dwg. RESULTS §2 named the unlock: "Promotion
  requires a purpose-built solid fixture DWG." This tool BUILDS that fixture
  headless, using only ops already probed RUNNABLE (plus one intentionally-
  degenerate empty-container create), chained through the sanctioned probe
  path -- so the fixture itself is evidence, reproducible from native_sample
  with one command.

MECHANISM (original READ-ONLY, staged copies all the way down):
  each step runs `tools/probe_reachability.py --probe-one <op> --fixture-json
  <args> --dwg <prev staged_result>`; cadctl stages a copy, the native layer
  _QSAVEs the ROUTER's staged copy, and the envelope reports it back as
  `staged_result`. Step N+1 stages from step N's staged_result, so the source
  fixture is never touched (probe_reachability additionally sha-verifies the
  original every step and hard-fails on mutation). Steps run SEQUENTIALLY --
  concurrent probes are a proven false-CRASH source (ledger P3b, offset case).

OUTPUT:
  tests/fixtures/enriched_seed_20260716.dwg   (+ .sha256)
  measure/reachable_fixtures/enriched_manifest.json  -- per-step op, args,
      created handle, staged sha; THE handle source for enriched fixtures
      (fixture args must cite this manifest, never guess handles).

Usage:
    python tools/build_enriched_fixture.py [--source tests/fixtures/native_sample.dwg]
Exit 0 = fixture built + manifest written; 1 = a chain step failed (fail-loud,
no partial fixture is published).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROBE = os.path.join(_REPO, "tools", "probe_reachability.py")
_SOURCE = os.path.join(_REPO, "tests", "fixtures", "native_sample.dwg")
_OUT_DWG = os.path.join(_REPO, "tests", "fixtures", "enriched_seed_20260716.dwg")
_MANIFEST = os.path.join(_REPO, "measure", "reachable_fixtures", "enriched_manifest.json")
_RUN_DIR = os.path.join(_REPO, "runs", "p3b_tail", "enrich_chain")

_LAYER = "ARIADNE_P3B_TAIL"

# The chain. Every op here is probed RUNNABLE in reachable_matrix_20260714
# (define.assocaction.create is RUNNABLE_BUT_DEGENERATE = ZERO_ARG_BY_CONTRACT:
# creating the EMPTY action container is exactly its documented contract, and
# exactly the prerequisite state the assoc tail ops need). Args reuse the
# proven curated fixtures (probe_reachability inline FIXTURES / fragments) --
# never invented.
#   ref: name under which the created handle lands in the manifest.
_CHAIN = [
    {"ref": "solid_a", "op": "write.entity.solid3d.primitive",
     "args": {"layer": _LAYER, "primitive": "wedge", "x_len": 2.0, "y_len": 1.5, "z_len": 3.5}},
    {"ref": "solid_b", "op": "write.entity.solid3d.primitive",
     "args": {"layer": _LAYER, "primitive": "wedge", "x_len": 2.0, "y_len": 1.5, "z_len": 3.5}},
    {"ref": "line_1", "op": "write.entity.line",
     "args": {"layer": _LAYER, "start": {"x": 1.0, "y": 2.0, "z": 0.0},
              "end": {"x": 11.0, "y": 12.0, "z": 0.0}}},
    {"ref": "line_2", "op": "write.entity.line",
     "args": {"layer": _LAYER, "start": {"x": 0.0, "y": 0.0, "z": 0.0},
              "end": {"x": 10.0, "y": 0.0, "z": 0.0}}},
    {"ref": "circle_1", "op": "write.entity.circle",
     "args": {"layer": _LAYER, "center": {"x": 12.0, "y": 14.0, "z": 0.0}, "radius": 3.5}},
    # state baked ONTO solid_a -- the solid create (m08gEmitCreate) returns its
    # handle in-envelope; line/circle creates use the older no-handle emit, so
    # their handles are harvested post-chain from the graph IR instead:
    {"ref": "ext_dict_on_solid_a", "op": "write.object.create_ext_dict",
     "args": {"handle": "@solid_a"}},
    {"ref": "xdata_on_solid_a", "op": "modify.entity.xdata",
     "args": {"handle": "@solid_a", "app_name": "ARIADNE_P3B_TAIL",
              "values": [{"code": 1000, "value": "p3b-tail-enriched"},
                          {"code": 1040, "value": 42.5}]}},
    {"ref": "layerstate", "op": "write.layerstate.save",
     "args": {"name": "ARIADNE_P3B_TAIL_LS", "description": "P3b tail enriched fixture layer state",
              "mask": ["all"], "overwrite": 1}},
    {"ref": "assoc_action", "op": "define.assocaction.create", "args": {}},
]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_refs(args, handles: dict):
    if isinstance(args, dict):
        return {k: _resolve_refs(v, handles) for k, v in args.items()}
    if isinstance(args, list):
        return [_resolve_refs(v, handles) for v in args]
    if isinstance(args, str) and args.startswith("@"):
        ref = args[1:]
        if ref not in handles:
            raise KeyError(f"chain ref '@{ref}' has no harvested handle yet")
        return handles[ref]
    return args


def run_chain(source: str) -> int:
    os.makedirs(_RUN_DIR, exist_ok=True)
    cur = source
    handles: dict[str, str] = {}
    steps_out = []
    for i, step in enumerate(_CHAIN, 1):
        out_dir = os.path.join(_RUN_DIR, f"e{i:02d}_{step['op'].replace('.', '_')}")
        args = _resolve_refs(step["args"], handles)
        cmd = [sys.executable, _PROBE, "--probe-one", step["op"],
               "--dwg", cur, "--out-dir", out_dir,
               "--fixture-json", json.dumps(args, ensure_ascii=False)]
        print(f"[e{i:02d}] {step['op']} <- {os.path.basename(cur)}")
        proc = subprocess.run(cmd, cwd=_REPO, capture_output=True, text=True, timeout=600)
        result_path = os.path.join(out_dir, "probe_result.json")
        if proc.returncode != 0 or not os.path.isfile(result_path):
            print(f"[e{i:02d}] FAIL: probe exit={proc.returncode}")
            print((proc.stderr or "")[-800:])
            return 1
        env = json.load(open(result_path, encoding="utf-8"))
        status = env.get("status")
        result = env.get("result") if isinstance(env.get("result"), dict) else {}
        staged = env.get("staged_result")
        if status != "ok" or not staged or not os.path.isfile(staged):
            print(f"[e{i:02d}] FAIL: status={status} staged_result={staged}")
            print(json.dumps(env, ensure_ascii=False)[:600])
            return 1
        handle = result.get("handle") or result.get("action_handle") or ""
        if handle:
            handles[step["ref"]] = handle
        steps_out.append({
            "step": i, "ref": step["ref"], "op": step["op"], "args": args,
            "status": status, "handle": handle or None,
            "result_keys": sorted(result.keys()),
            "staged_result_sha256": env.get("staged_result_sha256"),
            "probe_result": os.path.relpath(result_path, _REPO),
        })
        print(f"[e{i:02d}] ok handle={handle or '-'}")
        cur = staged

    # ---- post-chain harvest: graph IR of the final staged DWG -> handles the
    # older create emits did not return (lines/circle) + pre-existing state
    # (an INSERT, an MTEXT, an insertable block name) fixture authoring needs.
    harvest_dir = os.path.join(_RUN_DIR, "harvest_graph")
    cmd = [sys.executable, _PROBE, "--probe-one", "inspect.database.graph",
           "--dwg", cur, "--out-dir", harvest_dir, "--fixture-json", "{}"]
    print("[harvest] inspect.database.graph <- final staged")
    proc = subprocess.run(cmd, cwd=_REPO, capture_output=True, text=True, timeout=600)
    hres = os.path.join(harvest_dir, "probe_result.json")
    if proc.returncode != 0 or not os.path.isfile(hres):
        print(f"[harvest] FAIL: probe exit={proc.returncode}")
        return 1
    henv = json.load(open(hres, encoding="utf-8"))
    ir = henv.get("result") or {}
    if henv.get("status") != "ok" or not isinstance(ir.get("entities"), list):
        print(f"[harvest] FAIL: status={henv.get('status')}")
        return 1

    def _near(pt, x, y, z, tol=1e-6):
        return (isinstance(pt, (list, tuple)) and len(pt) >= 3
                and abs(pt[0] - x) < tol and abs(pt[1] - y) < tol and abs(pt[2] - z) < tol)

    first_insert = first_mtext = None
    xdata_app_confirmed = False
    for e in ir["entities"]:
        cls = e.get("dxf_name") or ""
        if e.get("layer") == _LAYER:
            if cls == "AcDbLine":
                if _near(e.get("start"), 1.0, 2.0, 0.0):
                    handles["line_1"] = e.get("handle")
                elif _near(e.get("start"), 0.0, 0.0, 0.0):
                    handles["line_2"] = e.get("handle")
            elif cls == "AcDbCircle":
                handles["circle_1"] = e.get("handle")
            if e.get("handle") == handles.get("solid_a"):
                xdata_app_confirmed = any(x.get("app") == "ARIADNE_P3B_TAIL"
                                          for x in (e.get("xdata") or []))
        if first_insert is None and cls == "AcDbBlockReference":
            first_insert = e
        if first_mtext is None and cls == "AcDbMText":
            first_mtext = e
    if first_insert is not None:
        handles["preexisting_insert"] = first_insert.get("handle")
        handles["preexisting_insert_block"] = (first_insert.get("name")
                                               or first_insert.get("block_name")
                                               or first_insert.get("block"))
    if first_mtext is not None:
        handles["preexisting_mtext"] = first_mtext.get("handle")
    if not xdata_app_confirmed:
        print("[harvest] FAIL: solid_a carries no ARIADNE_P3B_TAIL xdata in the IR "
              "(get_xdata promotion would be degenerate)")
        return 1
    for name in ("line_1", "line_2", "circle_1"):
        if name not in handles:
            print(f"[harvest] FAIL: could not locate '{name}' in graph IR (layer {_LAYER})")
            return 1
    print(f"[harvest] ok: {json.dumps({k: v for k, v in handles.items()}, ensure_ascii=False)}")

    shutil.copyfile(cur, _OUT_DWG)
    sha = _sha256(_OUT_DWG)
    with open(_OUT_DWG + ".sha256", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{sha}  {os.path.basename(_OUT_DWG)}\n")
    manifest = {
        "schema": "ariadne.p3b.enriched_fixture_manifest.v1",
        "source_fixture": os.path.relpath(source, _REPO),
        "source_sha256": _sha256(source),
        "output_fixture": os.path.relpath(_OUT_DWG, _REPO),
        "output_sha256": sha,
        "builder": "tools/build_enriched_fixture.py (sequential sanctioned-probe chain)",
        "handles": handles,
        "steps": steps_out,
    }
    with open(_MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"[done] {os.path.relpath(_OUT_DWG, _REPO)} sha256={sha[:16]}...")
    print(f"[done] handles: {json.dumps(handles, ensure_ascii=False)}")
    print(f"[done] manifest: {os.path.relpath(_MANIFEST, _REPO)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=_SOURCE)
    args = ap.parse_args()
    if not os.path.isfile(args.source):
        print(f"source fixture not found: {args.source}")
        return 1
    return run_chain(args.source)


if __name__ == "__main__":
    sys.exit(main())
