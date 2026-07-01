#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/fixture_foundry.py -- F10: per-kind golden source fixture foundry.

RT-FOLD R3-G9/R1-7 (see D:\\dev\\.build\\cados_plan\\final\\PLAN.md, node F10). The
WAVE-0 pilot corpus (``tests/fixtures/native_sample.dwg``) exercises 0 of the 13
new entity kinds and 0 of the ASM-dependent "hard" kinds (G9) -- every read/write
node for those kinds is currently accept-by-assertion, not accept-by-evidence.

This module closes that gap with one pipeline per kind:

    Lane-A create (``cadctl.Cad.run_operation``, ``write_copy``, on a STAGED copy)
        -> re-inspect (a FRESH ``cadctl.Cad.inspect(..., include_rich=True)`` that
           re-opens the SAVED staged file and re-extracts it, then
           ``cadctl.Cad.get_entity`` looks the created handle back up)
        -> commit a golden fixture (``fixtures/kinds/<kind>.dwg`` + a sha256
           sidecar), ONLY if every gate above passed.

"Lane A" / "Lane B" is the router's own vocabulary (PLAN.md PART 1 SS1.2): Lane A
is the native op surface (``cad_run_operation`` / ``cadctl.Cad.run_operation``);
this module never touches Lane B (the patch/roundtrip surface).

No-fake-success (Rule 12): the create op's own envelope is NOT trusted --
``cadctl.Cad.run_operation`` reports envelope ``status=='ok'`` as soon as ANY
native result JSON parses, even a ``MISSING_ARG``/native error (see
``cadctl.Cad.run_operation``). The only truthful signal is the native ``result``
payload itself (``created:true`` + ``errorstatus:0`` + a handle), AND a
re-inspect that independently re-finds that handle after a fresh reload. A kind
that fails any gate is UNVERIFIED and gets NO fixture file -- never a fabricated
one (a kind with no fixture stays UNVERIFIED, is never reported as passed).

Scope boundary (read this before "fixing" a kind): F10 proves PERSISTENCE (the
entity round-trips through an actual save + independent reload), not deep
geometric non-degeneracy (volume/topology/watertightness). That deeper assertion
belongs to T3a.8 / T9, which consume F10's fixture as their known-good input
(PLAN.md SS "T3a.8 ... solid extracts non-empty topology on F10 fixture"). Two of
the four "hard" kinds genuinely cannot be more than that today:
  * ``nurbsurface`` -- the current native handler ignores all job args and always
    builds the same hardcoded 2x2 unit-square bilinear patch (non-degenerate by
    construction, but not parametrizable from here).
  * ``body`` -- the current native handler has NO geometry-populating call at all
    (a bare ``AcDbBody`` is appended); it is structurally degenerate. This
    foundry still mints it, but as an explicit NEGATIVE CONTROL
    (``expected_non_degenerate: False``) for T3a.8/T9's non-degeneracy gate --
    never reported as a populated solid.

Live minting needs the CAD runtime (accoreconsole via the router). This module
builds the full harness + the per-kind manifest now, independent of runtime
availability; ``tests/unit/test_fixture_foundry.py`` proves the core logic with
``run_job.run_router_cad_job`` monkeypatched (the same technique already used by
``tests/unit/test_patch_engine_policy.py::TestApplyStagedLifecycleMocked`` --
never a hand-rolled fake client interface). ``deferred_mint_commands()`` prints
the exact CLI invocation for each kind for whoever runs this WITH the runtime.

Standard library only (stdlib json/hashlib/pathlib). Config JSON on this box is
BOM-prefixed elsewhere in this repo; this module reads none, so that gotcha does
not apply here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_ROOT = _THIS_DIR.parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import cadctl  # noqa: E402

SCHEMA_MINT_RESULT = "ariadne.cad_os.f10.mint_result.v1"
SCHEMA_MANIFEST_RUN = "ariadne.cad_os.f10.manifest_run.v1"
SCHEMA_STATUS = "ariadne.cad_os.f10.status.v1"

DEFAULT_SEED_DWG = str(_ROOT / "tests" / "fixtures" / "native_sample.dwg")
DEFAULT_FIXTURES_DIR = _ROOT / "fixtures" / "kinds"
DEFAULT_RUNS_DIR = _ROOT / "runs" / "fixture_foundry"

# ---------------------------------------------------------------------------
# KIND_MANIFEST -- the per-kind valid-arg manifest (the F10 deliverable). Every
# arg key is grounded in the native handler's own arg-parsing, NOT guessed:
# src/Ariadne.AcadNative/families/m08g_handlers.inc (m08gDispatch, one branch
# per op_id). Args are deliberately NON-empty/non-default -- the empty-arg
# RUNNABLE_BUT_DEGENERATE control probe is F1's job, not F10's; F10 fixtures
# must demonstrate a genuine, deliberately-constructed, non-degenerate entity.
# ---------------------------------------------------------------------------
KIND_MANIFEST: dict[str, dict[str, Any]] = {
    # ---- 13 new entity kinds (T3a.6) -------------------------------------
    "ellipse": {
        "op_id": "write.entity.ellipse",
        "args": {
            "center": {"x": 0.0, "y": 0.0, "z": 0.0},
            "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
            "major_axis": {"x": 2.0, "y": 0.0, "z": 0.0},
            "radius_ratio": 0.5,
            "start_angle": 0.0,
            "end_angle": 6.283185307179586,
            "layer": "0",
        },
    },
    "point": {
        "op_id": "write.entity.point",
        "args": {"position": {"x": 5.0, "y": 5.0, "z": 0.0}, "layer": "0"},
    },
    "spline": {
        "op_id": "write.entity.spline",
        "args": {
            "points": [
                {"x": 0.0, "y": 0.0, "z": 0.0},
                {"x": 5.0, "y": 8.0, "z": 0.0},
                {"x": 10.0, "y": 0.0, "z": 0.0},
                {"x": 15.0, "y": 8.0, "z": 0.0},
            ],
            "order": 4,
            "layer": "0",
        },
        "note": "fit-point spline (>=2 points); NOT the NURBS control-point/"
                "knot-vector form (G5) -- that variant is a separate, deeper "
                "field-manifest item owned by T3a.6, not this fixture.",
    },
    "ray": {
        "op_id": "write.entity.ray",
        "args": {
            "base": {"x": 0.0, "y": 0.0, "z": 0.0},
            "direction": {"x": 1.0, "y": 0.0, "z": 0.0},
            "layer": "0",
        },
        "note": "direction must be non-zero-length -- a zero direction is "
                "silently skipped by the handler (setUnitDir is never called), "
                "leaving an unverified default; args below use an explicit "
                "unit vector so the create is deliberately non-degenerate.",
    },
    "xline": {
        "op_id": "write.entity.xline",
        "args": {
            "base": {"x": 0.0, "y": 0.0, "z": 0.0},
            "direction": {"x": 1.0, "y": 1.0, "z": 0.0},
            "layer": "0",
        },
        "note": "same zero-direction caveat as ray (shared m08gVector default).",
    },
    "mline": {
        "op_id": "write.entity.mline",
        "args": {
            "points": [
                {"x": 0.0, "y": 0.0, "z": 0.0},
                {"x": 10.0, "y": 0.0, "z": 0.0},
                {"x": 10.0, "y": 10.0, "z": 0.0},
            ],
            "scale": 1.0,
            "closed": 0,
            "layer": "0",
        },
        "note": "uses the database default MLINE style (cmlstyleID); no "
                "explicit style is authored here.",
    },
    "trace": {
        "op_id": "write.entity.trace",
        "args": {
            "p0": {"x": 0.0, "y": 0.0, "z": 0.0},
            "p1": {"x": 4.0, "y": 0.0, "z": 0.0},
            "p2": {"x": 4.0, "y": 2.0, "z": 0.0},
            "p3": {"x": 0.0, "y": 2.0, "z": 0.0},
            "layer": "0",
        },
    },
    "solid2d": {
        "op_id": "write.entity.solid2d",
        "args": {
            "p0": {"x": 0.0, "y": 0.0, "z": 0.0},
            "p1": {"x": 3.0, "y": 0.0, "z": 0.0},
            "p2": {"x": 3.0, "y": 3.0, "z": 0.0},
            "p3": {"x": 0.0, "y": 3.0, "z": 0.0},
            "layer": "0",
        },
        "note": "legacy DXF SOLID quad (AcDbTrace-shaped data), not the ASM "
                "AcDbRegion/AcDb3dSolid family.",
    },
    "region": {
        "op_id": "write.entity.region",
        "args": {"layer": "0"},
        "prereq": {
            "op_id": "write.entity.circle",
            "args": {
                "center": {"x": 0.0, "y": 0.0, "z": 0.0},
                "radius": 3.0,
                "layer": "0",
            },
            "wire_into": "curves",
            "wire_as": "list",
        },
        "note": "AcDbRegion::createFromCurves requires an existing coplanar "
                "closed curve by handle (curves:[<handle>]); this foundry "
                "first Lane-A creates a circle on the seed and wires its "
                "returned handle into the region's args before the second "
                "Lane-A create.",
    },
    "wipeout": {
        "op_id": "write.entity.wipeout",
        "args": {
            "points": [
                {"x": 0.0, "y": 0.0, "z": 0.0},
                {"x": 6.0, "y": 0.0, "z": 0.0},
                {"x": 6.0, "y": 4.0, "z": 0.0},
                {"x": 0.0, "y": 4.0, "z": 0.0},
            ],
            "layer": "0",
        },
    },
    "shape": {
        "op_id": "write.entity.shape",
        "args": {
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "size": 1.0,
            "rotation": 0.0,
            "width_factor": 1.0,
            "name": "ARIADNE",
            "layer": "0",
        },
        "note": "name/shape_number are not validated against the active text "
                "style's loaded SHX at creation time; re-inspect here proves "
                "the AcDbShape entity persists, not that it resolves to a "
                "visible glyph (a real compiled SHX resource is out of scope).",
    },
    "rasterimage": {
        "op_id": "write.entity.rasterimage",
        "args": {
            "image_path": None,
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "width": 4.0,
            "height": 3.0,
            "name": "ARIADNE_IMAGE",
            "layer": "0",
        },
        "requires_asset": "image_path",
        "note": "requires a real image file on disk; no image asset ships "
                "with this repo. mint_fixture() refuses BEFORE touching the "
                "CAD runtime (status reason 'missing_asset') until a real "
                "path is supplied (CLI: --asset-image <path>).",
    },
    "mpolygon": {
        "op_id": "write.entity.mpolygon",
        "args": {
            "points": [
                {"x": 0.0, "y": 0.0, "z": 0.0},
                {"x": 5.0, "y": 0.0, "z": 0.0},
                {"x": 5.0, "y": 5.0, "z": 0.0},
                {"x": 0.0, "y": 5.0, "z": 0.0},
            ],
            "layer": "0",
        },
    },
    # ---- hard kinds: ASM/modeler-dependent (0.1 FAKE-SUCCESS evidence; ------
    # ---- barriered behind the B6 ASM non-degeneracy gate, C-ASM row) --------
    "solid3d": {
        "op_id": "write.entity.solid3d.primitive",
        "args": {"primitive": "box", "x": 2.0, "y": 2.0, "z": 2.0, "layer": "0"},
        "hard": True,
        "note": "representative op is write.entity.solid3d.primitive "
                "(primitive='box'; the one solid3d variant noted as "
                "'creates headless [V]' in PLAN.md T9). The "
                "extrude/revolve/sweep/loft variants are separate, "
                "ASM-riskier op_ids (0.1 FAKE SUCCESS on empty args) owned by "
                "T9's non-degeneracy probe, not this per-kind fixture.",
    },
    "surface": {
        "op_id": "write.entity.surface",
        "args": {"width": 3.0, "height": 2.0, "layer": "0"},
        "hard": True,
    },
    "nurbsurface": {
        "op_id": "write.entity.nurbsurface",
        "args": {"layer": "0"},
        "hard": True,
        "note": "the current handler ignores all job args and always builds "
                "the same hardcoded 2x2 control-point unit-square bilinear "
                "patch (non-degenerate by construction: a real, if minimal, "
                "surface). Args are accepted for manifest symmetry only.",
    },
    "body": {
        "op_id": "write.entity.body",
        "args": {"layer": "0"},
        "hard": True,
        "expected_non_degenerate": False,
        "role": "negative_control",
        "note": "write.entity.body has NO geometry-populating call in the "
                "current handler (a bare AcDbBody is appended) -- it is "
                "structurally degenerate by construction; no args can fix "
                "this from here. Minted anyway as an explicit NEGATIVE "
                "CONTROL for T3a.8/T9's non-degeneracy gate (it must report "
                "this fixture as EMPTY topology); never reported as a "
                "populated solid.",
    },
}

HARD_KINDS = tuple(k for k, spec in KIND_MANIFEST.items() if spec.get("hard"))
NEW_KINDS = tuple(k for k in KIND_MANIFEST if k not in HARD_KINDS)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: str | Path, payload: dict) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(p)


def _retry_transient_windows_io(fn, *, attempts: int = 5, delay_s: float = 0.05):
    """Retry `fn()` a few times on a transient Windows sharing violation.

    cadctl.Cad.run_operation()/inspect() each stage a fresh copy via a bare
    ``shutil.copy2`` with no try/except around it (that staging step is
    shared infrastructure this node does not own -- not this module's to
    patch). Observed empirically on this box: chaining a create's staged
    output straight into a re-inspect (this module's whole point) can hit
    WinError 32 (ERROR_SHARING_VIOLATION -- typically real-time antivirus
    briefly holding a just-written small file) on the very next copy. This
    is a transient OS condition, not a logic error, so we retry at the call
    site with a short backoff instead of silently swallowing it forever.
    """
    last_exc: PermissionError | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except PermissionError as exc:
            last_exc = exc
            if attempt + 1 >= attempts:
                raise
            time.sleep(delay_s * (attempt + 1))
    raise last_exc  # pragma: no cover -- unreachable (loop always returns or raises)


def _wire_handle(args: dict, prereq_spec: dict, handle: str) -> dict:
    """Return args with the prereq's handle wired in (list or scalar)."""
    out = dict(args)
    key = prereq_spec.get("wire_into", "handle")
    if prereq_spec.get("wire_as") == "list":
        out[key] = [handle]
    else:
        out[key] = handle
    return out


# ---------------------------------------------------------------------------
# Lane-A create (cadctl.Cad.run_operation) -- one honest interpretation point
# ---------------------------------------------------------------------------

def _lane_a_create(cad, op_id: str, args: dict, dwg_path: str, out_dir: str | Path) -> dict:
    """Run one Lane-A create on a staged copy; return an honest interpretation.

    Returns {"ok", "reason", "handle", "envelope", "staged_copy"}. "ok" is True
    ONLY when the native result explicitly reports created:true, errorstatus 0
    (when present), and a handle. cadctl's own envelope status is NEVER
    trusted alone -- run_operation reports status=='ok' as soon as ANY native
    result JSON parses, including a MISSING_ARG / native error payload (see
    cadctl.Cad.run_operation: native_status falls back to "ok" when the inner
    result has no "status" key of its own).
    """
    envelope = cad.run_operation(
        op_id, args=dict(args), write_mode="write_copy",
        dwg_path=dwg_path, out_dir=str(out_dir),
    )
    out: dict[str, Any] = {
        "ok": False, "reason": "", "handle": None, "envelope": envelope,
        "staged_copy": envelope.get("staged_copy") if isinstance(envelope, dict) else None,
    }
    if not isinstance(envelope, dict) or not envelope.get("executed"):
        reason = envelope.get("reason") if isinstance(envelope, dict) else None
        out["reason"] = reason or "operation was not executed (registry/write-mode refusal)"
        return out
    if not envelope.get("original_unchanged", True):
        out["reason"] = "SAFETY: source DWG changed during Lane-A create -- refusing to mint"
        return out
    result = envelope.get("result")
    if not isinstance(result, dict):
        out["reason"] = envelope.get("reason") or "no native result object returned"
        return out
    if result.get("error_code") or result.get("status") == "error":
        out["reason"] = str(result.get("error") or result.get("error_code") or "native error")
        return out
    if result.get("created") is not True:
        out["reason"] = "native result did not report created:true"
        return out
    if "errorstatus" in result and result.get("errorstatus") != 0:
        out["reason"] = "errorstatus=%r" % (result.get("errorstatus"),)
        return out
    handle = result.get("handle")
    if not handle:
        # region's m08gAppendPieces envelope has no singular "handle" -- it
        # emits {"region_count":N, "handles":[...]} instead (see
        # write.entity.region in m08g_handlers.inc). Take the first appended
        # handle as the fixture's representative entity.
        handles = result.get("handles")
        if isinstance(handles, list) and handles:
            handle = handles[0]
    if not handle:
        out["reason"] = "created:true but no handle (or handles[]) returned"
        return out
    out["ok"] = True
    out["handle"] = handle
    return out


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def mint_fixture(kind: str, *, seed_dwg: str = DEFAULT_SEED_DWG,
                  fixtures_dir: str | Path = DEFAULT_FIXTURES_DIR,
                  run_root: str | Path | None = None, cad=None) -> dict:
    """Lane-A create -> re-inspect -> commit ONE golden per-kind fixture.

    Never fabricates: ANY failure at any gate returns a record with
    status='UNVERIFIED' and writes NO fixture/sha for `kind` -- a kind with no
    fixture stays UNVERIFIED, never reported as passed (F10 hard rule).
    """
    cad = cad or cadctl.Cad()
    spec = KIND_MANIFEST.get(kind)
    run_root_p = Path(run_root) if run_root else (DEFAULT_RUNS_DIR / _ts() / kind)
    run_root_p.mkdir(parents=True, exist_ok=True)

    record: dict[str, Any] = {
        "schema": SCHEMA_MINT_RESULT,
        "kind": kind,
        "status": "UNVERIFIED",
        "verified": False,
        "reason": None,
        "op_id": None,
        "args": None,
        "handle": None,
        "fixture_path": None,
        "sha256": None,
        "hard_kind": False,
        "role": "fixture",
        "run_dir": str(run_root_p),
        "minted_at": _now_iso(),
    }
    if spec is None:
        record["reason"] = "unknown kind %r -- not in KIND_MANIFEST" % (kind,)
        return record

    record["op_id"] = spec["op_id"]
    record["hard_kind"] = bool(spec.get("hard"))
    record["role"] = spec.get("role", "fixture")

    # Asset precondition (rasterimage): refuse BEFORE touching the CAD runtime.
    asset_key = spec.get("requires_asset")
    if asset_key:
        asset_path = spec["args"].get(asset_key)
        if not asset_path or not Path(asset_path).is_file():
            record["reason"] = "missing_asset: no valid file for %r (got %r)" % (
                asset_key, asset_path)
            return record

    dwg_for_create = str(seed_dwg)
    if not Path(dwg_for_create).is_file():
        record["reason"] = "seed DWG not found: %s" % (dwg_for_create,)
        return record
    args = dict(spec["args"])

    # --- prereq: some kinds (region) reference a handle that must exist first.
    prereq_spec = spec.get("prereq")
    if prereq_spec:
        prereq_dir = run_root_p / "prereq"
        prereq = _retry_transient_windows_io(lambda: _lane_a_create(
            cad, prereq_spec["op_id"], prereq_spec["args"], dwg_for_create, prereq_dir))
        _write_json(prereq_dir / "lane_a_create.json", prereq)
        record["prereq"] = {"op_id": prereq_spec["op_id"], "ok": prereq["ok"]}
        if not prereq["ok"]:
            record["reason"] = "prereq %r failed: %s" % (prereq_spec["op_id"], prereq["reason"])
            return record
        record["prereq"]["handle"] = prereq["handle"]
        # Chain onto the prereq's OWN staged copy so the create sees the new curve.
        if prereq["staged_copy"]:
            dwg_for_create = prereq["staged_copy"]
        args = _wire_handle(args, prereq_spec, prereq["handle"])

    # --- Lane-A create on a staged copy ---
    create_dir = run_root_p / "create"
    create = _retry_transient_windows_io(lambda: _lane_a_create(
        cad, spec["op_id"], args, dwg_for_create, create_dir))
    _write_json(create_dir / "lane_a_create.json", create)
    record["args"] = args
    if not create["ok"]:
        record["reason"] = "Lane-A create not confirmed: %s" % (create["reason"],)
        return record
    handle = create["handle"]
    record["handle"] = handle
    staged_with_entity = create["staged_copy"]
    if not staged_with_entity or not Path(staged_with_entity).is_file():
        record["reason"] = "create reported success but no staged copy file was produced"
        return record

    # --- re-inspect: a FRESH process re-opens the staged file and re-extracts.
    reinspect_dir = run_root_p / "reinspect"
    insp_env = _retry_transient_windows_io(lambda: cad.inspect(
        staged_with_entity, str(reinspect_dir), mode="rich", include_rich=True))
    _write_json(reinspect_dir / "inspect_envelope.json", insp_env)
    if not isinstance(insp_env, dict) or insp_env.get("status") != "ok" or not insp_env.get("dwg_graph_ir"):
        insp_status = insp_env.get("status") if isinstance(insp_env, dict) else None
        insp_reason = insp_env.get("reason") if isinstance(insp_env, dict) else None
        record["reason"] = "re-inspect did not produce an IR: %s" % (insp_reason or insp_status)
        return record
    ir_path = insp_env["dwg_graph_ir"]
    entity_row = cad.get_entity(ir_path, handle)
    _write_json(reinspect_dir / "get_entity.json", entity_row)
    if not isinstance(entity_row, dict) or entity_row.get("status") != "ok" or not entity_row.get("row_count"):
        record["reason"] = ("re-inspect could not re-find handle %s after an independent "
                             "reload -- not proven persisted" % (handle,))
        return record

    # --- commit the golden fixture (reachable ONLY once every gate passed) ---
    fixtures_dir_p = Path(fixtures_dir)
    fixtures_dir_p.mkdir(parents=True, exist_ok=True)
    fixture_path = fixtures_dir_p / ("%s.dwg" % kind)
    _retry_transient_windows_io(lambda: shutil.copy2(staged_with_entity, fixture_path))
    sha = _sha256_file(fixture_path)
    (fixtures_dir_p / ("%s.dwg.sha256" % kind)).write_text(sha + "\n", encoding="utf-8")

    record.update({
        "status": "VERIFIED",
        "verified": True,
        "reason": None,
        "fixture_path": str(fixture_path),
        "sha256": sha,
        "reinspect_ref": str(reinspect_dir / "get_entity.json"),
    })
    if spec.get("expected_non_degenerate") is False:
        record["status"] = "VERIFIED_NEGATIVE_CONTROL"
        record["expected_non_degenerate"] = False
    return record


def mint_all(kinds: list[str] | None = None, *, seed_dwg: str = DEFAULT_SEED_DWG,
             fixtures_dir: str | Path = DEFAULT_FIXTURES_DIR,
             run_root: str | Path | None = None, cad=None) -> dict:
    """Mint every requested kind (default: every kind in KIND_MANIFEST)."""
    kinds = list(KIND_MANIFEST) if kinds is None else list(kinds)
    cad = cad or cadctl.Cad()
    run_root_p = Path(run_root) if run_root else (DEFAULT_RUNS_DIR / _ts())
    results = [
        mint_fixture(k, seed_dwg=seed_dwg, fixtures_dir=fixtures_dir,
                     run_root=run_root_p / k, cad=cad)
        for k in kinds
    ]
    verified = sum(1 for r in results if r["verified"])
    payload = {
        "schema": SCHEMA_MANIFEST_RUN,
        "total": len(results),
        "verified_count": verified,
        "unverified_count": len(results) - verified,
        "all_verified": verified == len(results),
        "results": results,
    }
    _write_json(run_root_p / "manifest_run.json", payload)
    return payload


def foundry_status(fixtures_dir: str | Path = DEFAULT_FIXTURES_DIR) -> dict:
    """Report VERIFIED/UNVERIFIED for every kind in KIND_MANIFEST.

    VERIFIED requires a fixture .dwg file AND a .sha256 sidecar whose recorded
    hash matches the file's current content -- a kind with no fixture (or a
    stale/tampered one) is UNVERIFIED, never reported as passed.
    """
    fixtures_dir_p = Path(fixtures_dir)
    kinds_out = []
    verified = 0
    for kind, spec in KIND_MANIFEST.items():
        fixture_path = fixtures_dir_p / ("%s.dwg" % kind)
        sha_path = fixtures_dir_p / ("%s.dwg.sha256" % kind)
        present = fixture_path.is_file() and sha_path.is_file()
        sha_recorded = sha_path.read_text(encoding="utf-8").strip() if sha_path.is_file() else None
        sha_actual = _sha256_file(fixture_path) if fixture_path.is_file() else None
        matches = bool(present and sha_recorded and sha_recorded == sha_actual)
        status = "VERIFIED" if matches else "UNVERIFIED"
        if matches and spec.get("expected_non_degenerate") is False:
            status = "VERIFIED_NEGATIVE_CONTROL"
        kinds_out.append({
            "kind": kind,
            "op_id": spec["op_id"],
            "hard_kind": bool(spec.get("hard")),
            "fixture_present": present,
            "sha_matches": matches,
            "status": status,
        })
        if matches:
            verified += 1
    return {
        "schema": SCHEMA_STATUS,
        "fixtures_dir": str(fixtures_dir_p),
        "total_kinds": len(KIND_MANIFEST),
        "verified_count": verified,
        "unverified_count": len(KIND_MANIFEST) - verified,
        "all_verified": verified == len(KIND_MANIFEST),
        "kinds": kinds_out,
    }


def deferred_mint_command(kind: str, *, seed_dwg: str = DEFAULT_SEED_DWG,
                          fixtures_dir: str | Path = DEFAULT_FIXTURES_DIR) -> str:
    """The exact CLI invocation to mint ONE kind once the CAD runtime is live."""
    if kind not in KIND_MANIFEST:
        raise KeyError("unknown kind %r -- not in KIND_MANIFEST" % (kind,))
    cmd = (
        'python tools/fixture_foundry.py mint --kind %s --seed "%s" --out "%s"'
        % (kind, seed_dwg, fixtures_dir)
    )
    if KIND_MANIFEST[kind].get("requires_asset"):
        cmd += ' --asset-image "<path-to-a-real-image-file>"'
    return cmd


def deferred_mint_commands(*, seed_dwg: str = DEFAULT_SEED_DWG,
                           fixtures_dir: str | Path = DEFAULT_FIXTURES_DIR) -> list[str]:
    """One exact deferred mint command per manifest kind, in manifest order."""
    return [deferred_mint_command(k, seed_dwg=seed_dwg, fixtures_dir=fixtures_dir)
            for k in KIND_MANIFEST]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fixture_foundry.py",
                                  description="F10 -- per-kind golden fixture foundry")
    sub = ap.add_subparsers(dest="command", required=True)

    mint = sub.add_parser("mint", help="Lane-A create -> re-inspect -> commit fixture(s)")
    mint.add_argument("--kind", action="append", dest="kinds",
                      help="kind name (repeatable); omit with --all for every kind")
    mint.add_argument("--all", action="store_true", help="mint every kind in KIND_MANIFEST")
    mint.add_argument("--seed", default=DEFAULT_SEED_DWG, help="seed DWG to stage from")
    mint.add_argument("--out", default=str(DEFAULT_FIXTURES_DIR), help="fixtures output dir")
    mint.add_argument("--asset-image", dest="asset_image", default=None,
                      help="real image file path for the rasterimage kind")

    status_p = sub.add_parser("status", help="report VERIFIED/UNVERIFIED per kind")
    status_p.add_argument("--out", default=str(DEFAULT_FIXTURES_DIR), help="fixtures dir to check")

    deferred = sub.add_parser("deferred-commands",
                              help="print the exact per-kind mint command (runtime-gated)")
    deferred.add_argument("--seed", default=DEFAULT_SEED_DWG)
    deferred.add_argument("--out", default=str(DEFAULT_FIXTURES_DIR))

    args = ap.parse_args(argv)

    if args.command == "mint":
        if args.asset_image:
            KIND_MANIFEST["rasterimage"]["args"]["image_path"] = args.asset_image
        kinds = list(KIND_MANIFEST) if args.all else (args.kinds or [])
        if not kinds:
            ap.error("mint requires --kind <k> (repeatable) or --all")
        payload = mint_all(kinds, seed_dwg=args.seed, fixtures_dir=args.out)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["all_verified"] else 1

    if args.command == "status":
        out = foundry_status(args.out)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out["all_verified"] else 1

    if args.command == "deferred-commands":
        for cmd in deferred_mint_commands(seed_dwg=args.seed, fixtures_dir=args.out):
            print(cmd)
        return 0

    ap.error("no command dispatched")
    return 2  # unreachable


if __name__ == "__main__":
    raise SystemExit(_main())
