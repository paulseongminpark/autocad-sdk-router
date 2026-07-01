#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""op_roundtrip_probe.py -- CAD OS Layer WAVE-0 F3: the op_id -> P-gate driver.

``cad_op_gate.py`` is pure judge logic (dict-in, dict-out; fully unit-testable
without a live CAD runtime). THIS module is the thin, op-aware DRIVER that
feeds it real staged-write results:

  1. ``resolve_native_op`` -- a patch op_name (e.g. ``"create_line"``) maps to
     its native ObjectARX op_id via ``tools/patch_ops`` (F9's split registry,
     already merged). An op_name with NO live handler fails HERE, before any
     disk/process activity -- this is the "exit 3 on not-wired" acceptance
     case, checked first and unconditionally.
  2. ``expected_ir_for_op`` -- builds the single-entity "ground truth" IR
     directly from the op's OWN args (the geometry we ASKED to be written --
     never a live read). This is the P-gate's ``expected_ir``.
  3. ``probe_roundtrip`` -- drives ``patch_engine.apply_staged`` (already
     merged: staging, the real ObjectARX write, pre/post-inspect, cad_diff,
     validate, and the original-unchanged proof) to mutate a STAGED COPY and
     extract the REAL pre/post IR. Injectable as ``apply_staged=`` purely for
     testability (mirrors ``cross_oracle.py``'s own ``router_extract``
     injection pattern) -- unit tests inject a fake envelope; LIVE callers get
     the real ``patch_engine.apply_staged`` by default.
  4. ``added_entities_ir`` -- resolves the diff's added-handle set back into
     FULL post-IR entity records (``cad_diff``'s ``changed_handles`` only
     carries handle/dxf_name/layer, not geometry) -- this is the P-gate's
     ``actual_ir``.
  5. hands ``(expected_ir, actual_ir)`` to ``cad_op_gate.check_roundtrip`` and
     folds in the original-unchanged proof ``apply_staged`` already computed.

Live-runtime status (Rule 12, no-fake-success)
------------------------------------------------
The LIVE leg genuinely shells out to accoreconsole via
``patch_engine.apply_staged -> run_job.run_router_cad_job`` (already-merged,
real router integration) -- it is NOT re-implemented here. This module's OWN
logic (op resolution / expected-entity construction / added-entity extraction
/ gate wiring) is fully exercised by
``tests/unit/test_op_roundtrip_probe.py`` against an INJECTED fake
``apply_staged`` (no accoreconsole invoked in CI/unit tests). A genuine
end-to-end run against a live, disposable staging DWG is DONE_NEEDS_RUNTIME:

    Deferred live command (run from this worktree root; AutoCAD 2027 present
    on this box, but a real staged write was not exercised in this build --
    provisioning a disposable scratch DWG + verifying the real ObjectARX
    write path is out of scope for a pure-logic unit-test gate):

        python tools/op_roundtrip_probe.py --op create_line \\
            --dwg <a real, disposable staging DWG path> \\
            --start 0 0 0 --end 100 0 0 --layer DIM \\
            --out-dir runs/f3_probe_live

Public API:
    resolve_native_op(op_name, patch_ops_mod=None) -> str | None
    expected_ir_for_op(op_name, args) -> dict
    added_entities_ir(pre_ir, post_ir, cad_diff_mod=None) -> dict
    probe_roundtrip(op_name, args, dwg_path, out_dir, apply_staged=None, ...) -> dict
    load_ir(path) -> dict                                        # BOM-tolerant

Run ``python tools/op_roundtrip_probe.py`` (no args) for a synthetic self-demo
against an injected fake ``apply_staged`` (no live runtime touched).
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable, Dict, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)

SCHEMA_ID = "ariadne.op_roundtrip_probe.v1"
IR_SCHEMA_ID = "ariadne.dwg_graph_ir.v1"
_JSON_ENCODING = "utf-8-sig"


def _import_optional(module_name: str):
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    try:
        return __import__(module_name)
    except Exception:  # pragma: no cover - defensive; sibling truly absent
        return None


def load_ir(path) -> Dict[str, Any]:
    """Load an IR JSON document (BOM-tolerant)."""
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _load_ir_maybe(value: Any) -> Dict[str, Any]:
    """``value`` is either an already-loaded IR dict (unit tests) or a path
    string (the real patch_engine.apply_staged envelope's extra.pre_ir/
    post_ir, which are on-disk JSON paths)."""
    if isinstance(value, dict):
        return value
    return load_ir(value)


# --------------------------------------------------------------------------- #
# 1. op resolution -- "exit 3 on not-wired" fires here
# --------------------------------------------------------------------------- #

def resolve_native_op(op_name: str, *, patch_ops_mod=None) -> Optional[str]:
    """patch op_name (e.g. ``"create_line"``) -> native op_id, or ``None`` if
    this patch op has no LIVE native write handler wired today
    (``patch_ops.NATIVE_WRITE_OP_MAP``, F9's split registry)."""
    mod = patch_ops_mod if patch_ops_mod is not None else _import_optional("patch_ops")
    if mod is None:
        return None
    return (getattr(mod, "NATIVE_WRITE_OP_MAP", None) or {}).get(op_name)


# --------------------------------------------------------------------------- #
# 2. expected-entity construction (ground truth = the op's own args, never a
#    live read)
# --------------------------------------------------------------------------- #

def _point_to_list(coords: Any) -> list:
    """The IR's OWN geometry representation is a plain ``[x, y, z]`` list (see
    ``added_entities_ir`` / the native extractor's ``actual_ir``) -- distinct
    from the job-args point-OBJECT shape schemas/cad_job.v2.schema.json
    requires (``{"x":.., "y":.., "z":..}``, confirmed by test_native/
    job_line_create.json). Accepts either shape so this stays correct for
    both CLI-built args (point-object, see ``_as_point_arg``) and any
    programmatic caller still passing a bare ``[x, y, z]``."""
    if isinstance(coords, dict):
        return [coords.get("x", 0.0), coords.get("y", 0.0), coords.get("z", 0.0)]
    return list(coords)


def _expect_create_line(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dxf_name": "LINE", "layer": args.get("layer") or "0",
        "geometry": {"kind": "line", "start": _point_to_list(args["start"]),
                    "end": _point_to_list(args["end"])},
    }


def _expect_create_circle(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dxf_name": "CIRCLE", "layer": args.get("layer") or "0",
        "geometry": {"kind": "circle", "center": _point_to_list(args["center"]),
                    "radius": args["radius"]},
    }


# op_name -> args -> a single IR entity (dxf_name/layer/geometry only -- no
# handle; the P-gate's geometry-basis compare is handle-independent by
# design). Only ops this module can honestly build ground truth for; an
# op_name outside this map is NOT_IMPLEMENTED here even if it happens to be
# wired natively (a real gap between "can write" and "can independently
# assert what SHOULD have been written" -- no-fake-success).
_EXPECTED_ENTITY_BUILDERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "create_line": _expect_create_line,
    "create_circle": _expect_create_circle,
}


def expected_ir_for_op(op_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """A minimal single-entity ``dwg_graph_ir.v1`` doc: the geometry ground
    truth the op's OWN args assert -- the P-gate's ``expected_ir``.

    Raises ``NotImplementedError`` for an ``op_name`` this module has no
    ground-truth builder for (a real gap, never silently guessed).
    """
    builder = _EXPECTED_ENTITY_BUILDERS.get(op_name)
    if builder is None:
        raise NotImplementedError(
            "no expected-entity builder for op_name %r (wired: %s)"
            % (op_name, sorted(_EXPECTED_ENTITY_BUILDERS)))
    return {"schema": IR_SCHEMA_ID, "entities": [builder(args)]}


# --------------------------------------------------------------------------- #
# 4. added-entity extraction: real post IR -> the single new FULL record
# --------------------------------------------------------------------------- #

def added_entities_ir(pre_ir: Dict[str, Any], post_ir: Dict[str, Any], *,
                      cad_diff_mod=None) -> Dict[str, Any]:
    """The IR-shaped subset of ``post_ir``'s entities whose handle is NEW
    relative to ``pre_ir`` (a handle-basis diff's 'added' set), resolved back
    into FULL entity records -- ``cad_diff``'s ``changed_handles`` only
    carries handle/dxf_name/layer, not the geometry the P-gate needs.
    """
    cd = cad_diff_mod if cad_diff_mod is not None else _import_optional("cad_diff")
    if cd is None or not hasattr(cd, "compute_diff"):
        raise RuntimeError("cad_diff sibling module unavailable")
    diff = cd.compute_diff(pre_ir, post_ir, comparison_basis="handle")
    added_handles = {r["handle"] for r in diff["changed_handles"] if r["change"] == "added"}
    post_by_handle = {e.get("handle"): e for e in (post_ir.get("entities") or []) if isinstance(e, dict)}
    entities = [post_by_handle[h] for h in sorted(added_handles) if h in post_by_handle]
    return {"schema": IR_SCHEMA_ID, "entities": entities}


# --------------------------------------------------------------------------- #
# 3./5. the driver: stage + write + inspect (patch_engine.apply_staged) ->
# P-gate judge (cad_op_gate.check_roundtrip)
# --------------------------------------------------------------------------- #

def _build_patch(op_name: str, args: Dict[str, Any], dwg_path: str, out_dir: str) -> Dict[str, Any]:
    # target_dwg is REQUIRED by schemas/cad_patch.v1.schema.json (staged_path
    # distinct from original_path). apply_staged's own create_staged_copy(dwg_path,
    # out_dir) always writes to <out_dir>/staged_input.dwg regardless of this
    # declared value (it does not read target_dwg to decide where to stage) --
    # so this is the TRUE path, not a placeholder, kept honest with what
    # create_staged_copy actually produces moments later.
    return {
        "schema": "ariadne.cad_patch.v1",
        "patch_id": "op_roundtrip_probe/%s" % op_name,
        "target_dwg": {
            "original_path": os.path.abspath(dwg_path),
            "staged_path": os.path.join(out_dir, "staged_input.dwg"),
        },
        "operations": [{"step_id": "s1", "operation": op_name, "args": args}],
        "postconditions": [{"subject": "entity_count", "op": "delta_eq", "value": 1}],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }


def probe_roundtrip(op_name: str, args: Dict[str, Any], dwg_path: str, out_dir: str, *,
                    apply_staged: Optional[Callable[[Dict[str, Any], str, str], Dict[str, Any]]] = None,
                    geometry_tolerance: Optional[float] = None,
                    patch_ops_mod=None, cad_diff_mod=None, cad_op_gate_mod=None) -> Dict[str, Any]:
    """Run the P-gate roundtrip probe for one ``create_*`` op against
    ``dwg_path``. See module docstring for the 5-step pipeline. Every non-OK
    outcome (not wired / apply_staged degraded / original mutated / geometry
    mismatch) returns a truthful ``cad_op_gate``-shaped result -- never a
    fake PASS.
    """
    gate = cad_op_gate_mod if cad_op_gate_mod is not None else _import_optional("cad_op_gate")
    if gate is None:
        return {"schema": SCHEMA_ID, "op_name": op_name, "status": "error", "exit_code": 2,
               "reason": "cad_op_gate sibling module unavailable"}

    native_op = resolve_native_op(op_name, patch_ops_mod=patch_ops_mod)
    if native_op is None:
        return {
            "schema": SCHEMA_ID, "op_name": op_name, "status": gate.STATUS_NOT_IMPLEMENTED,
            "exit_code": gate.EXIT_NOT_IMPLEMENTED,
            "reason": "op_name %r has no live native write handler wired "
                      "(patch_ops.NATIVE_WRITE_OP_MAP)" % op_name,
        }

    try:
        expected_ir = expected_ir_for_op(op_name, args)
    except NotImplementedError as exc:
        return {
            "schema": SCHEMA_ID, "op_name": op_name, "native_op": native_op,
            "status": gate.STATUS_NOT_IMPLEMENTED, "exit_code": gate.EXIT_NOT_IMPLEMENTED,
            "reason": str(exc),
        }

    apply_fn = apply_staged
    if apply_fn is None:
        patch_engine = _import_optional("patch_engine")
        apply_fn = getattr(patch_engine, "apply_staged", None) if patch_engine else None
    if apply_fn is None:
        return {
            "schema": SCHEMA_ID, "op_name": op_name, "native_op": native_op,
            "status": gate.STATUS_NOT_IMPLEMENTED, "exit_code": gate.EXIT_NOT_IMPLEMENTED,
            "reason": "patch_engine.apply_staged unavailable",
        }

    patch = _build_patch(op_name, args, dwg_path, out_dir)
    envelope = apply_fn(patch, dwg_path, out_dir)
    env_status = envelope.get("status")
    if env_status != "ok":
        deferred_reasons = {"not_implemented", "unavailable"}
        exit_code = gate.EXIT_NOT_IMPLEMENTED if env_status in deferred_reasons else gate.EXIT_ERROR
        status = gate.STATUS_NOT_IMPLEMENTED if env_status in deferred_reasons else gate.STATUS_ERROR
        return {
            "schema": SCHEMA_ID, "op_name": op_name, "native_op": native_op,
            "status": status, "exit_code": exit_code,
            "reason": envelope.get("reason"), "envelope_status": env_status,
        }

    orig = envelope.get("original_unchanged") or {}
    if orig and orig.get("unchanged") is False:
        return {
            "schema": SCHEMA_ID, "op_name": op_name, "native_op": native_op,
            "status": gate.STATUS_ORIGINAL_MUTATED, "exit_code": gate.EXIT_ORIGINAL_MUTATED,
            "reason": "original DWG changed during the live apply -- READ-ONLY invariant violated",
            "original_unchanged": orig,
        }

    # patch_engine.apply_staged's _result_envelope(..., extra=...) does
    # env.update(extra) -- i.e. extra fields land at the envelope's TOP LEVEL
    # (envelope["pre_ir"] / envelope["post_ir"]), there is no nested "extra" key.
    pre_ir_ref = envelope.get("pre_ir")
    post_ir_ref = envelope.get("post_ir")
    if not pre_ir_ref or not post_ir_ref:
        return {
            "schema": SCHEMA_ID, "op_name": op_name, "native_op": native_op,
            "status": gate.STATUS_ERROR, "exit_code": gate.EXIT_ERROR,
            "reason": "apply_staged envelope reported ok but is missing pre_ir/post_ir",
        }
    pre_ir = _load_ir_maybe(pre_ir_ref)
    post_ir = _load_ir_maybe(post_ir_ref)
    actual_ir = added_entities_ir(pre_ir, post_ir, cad_diff_mod=cad_diff_mod)

    tol = geometry_tolerance if geometry_tolerance is not None else gate.DEFAULT_GEOMETRY_TOLERANCE
    gate_result = gate.check_roundtrip(expected_ir, actual_ir, geometry_tolerance=tol,
                                       cad_diff_mod=cad_diff_mod)

    result = dict(gate_result)
    result.update({
        "schema": SCHEMA_ID, "op_name": op_name, "native_op": native_op,
        "expected_ir": expected_ir, "actual_ir": actual_ir,
        "original_unchanged": orig, "run_dir": out_dir,
    })
    return result


# --------------------------------------------------------------------------- #
# Self-demo (__main__ with no args): injected fake apply_staged, no live
# runtime touched -- proves the driver's OWN wiring end to end.
# --------------------------------------------------------------------------- #

def _fake_apply_staged_ok(op_name: str, entity: Dict[str, Any]):
    def _fn(patch, dwg_path, out_dir):
        pre_ir = {"schema": IR_SCHEMA_ID, "entities": []}
        post_entity = dict(entity)
        post_entity.setdefault("handle", "9F1")
        post_ir = {"schema": IR_SCHEMA_ID, "entities": [post_entity]}
        return {
            "status": "ok",
            "original_unchanged": {"unchanged": True},
            # top-level, mirroring the REAL patch_engine.apply_staged envelope
            # (_result_envelope(..., extra=...) does env.update(extra) --
            # there is no nested "extra" key in the real contract).
            "pre_ir": pre_ir, "post_ir": post_ir,
        }
    return _fn


def _selftest() -> int:
    print("== op_roundtrip_probe self-demo (injected apply_staged, no live runtime) ==")

    matching_entity = {
        "handle": "9F1", "dxf_name": "LINE", "layer": "DIM",
        "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [100.0, 0.0, 0.0]},
    }
    r_ok = probe_roundtrip(
        "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
        "fake.dwg", "fake_out",
        apply_staged=_fake_apply_staged_ok("create_line", matching_entity))
    print("matching roundtrip  : status=%s exit=%d (expect ok/0)" % (r_ok["status"], r_ok["exit_code"]))

    shifted_entity = {
        "handle": "9F1", "dxf_name": "LINE", "layer": "DIM",
        "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [100.0, 5.0, 0.0]},
    }
    r_shifted = probe_roundtrip(
        "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
        "fake.dwg", "fake_out",
        apply_staged=_fake_apply_staged_ok("create_line", shifted_entity))
    print("shifted roundtrip   : status=%s exit=%d (expect fail/1)"
         % (r_shifted["status"], r_shifted["exit_code"]))

    r_not_wired = probe_roundtrip(
        "create_arc", {}, "fake.dwg", "fake_out",
        apply_staged=_fake_apply_staged_ok("create_arc", matching_entity))
    print("not-wired op        : status=%s exit=%d (expect not_implemented/3)"
         % (r_not_wired["status"], r_not_wired["exit_code"]))

    passed = (r_ok["exit_code"] == 0 and r_shifted["exit_code"] == 1 and r_not_wired["exit_code"] == 3)
    print("RESULT              : %s" % ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="op_roundtrip_probe: op_id -> P-gate driver (F3). With no "
                    "arguments, runs an injected-apply_staged self-demo (no live runtime).")
    ap.add_argument("--op", dest="op_name", help="patch op_name, e.g. create_line")
    ap.add_argument("--dwg", dest="dwg_path", help="staging-source DWG path (LIVE leg)")
    ap.add_argument("--out-dir", dest="out_dir", help="run output directory (LIVE leg)")
    ap.add_argument("--start", nargs=3, type=float, metavar=("X", "Y", "Z"))
    ap.add_argument("--end", nargs=3, type=float, metavar=("X", "Y", "Z"))
    ap.add_argument("--center", nargs=3, type=float, metavar=("X", "Y", "Z"))
    ap.add_argument("--radius", type=float)
    ap.add_argument("--layer", default="0")
    args = ap.parse_args(argv)

    if not args.op_name or not args.dwg_path or not args.out_dir:
        return _selftest()

    def _point_arg(xyz):  # CLI [X, Y, Z] -> the {"x","y","z"} point-object
        return {"x": xyz[0], "y": xyz[1], "z": xyz[2]}  # shape write.entity.line/
        # circle actually require (schemas/cad_job.v2.schema.json + test_native/
        # job_line_create.json) -- a bare list is NOT recognized by the native
        # dispatcher and silently degenerates to a unit line/circle instead of
        # erroring, so this must match on the wire, not just satisfy Python.

    op_args: Dict[str, Any] = {"layer": args.layer}
    if args.start is not None:
        op_args["start"] = _point_arg(args.start)
    if args.end is not None:
        op_args["end"] = _point_arg(args.end)
    if args.center is not None:
        op_args["center"] = _point_arg(args.center)
    if args.radius is not None:
        op_args["radius"] = args.radius

    result = probe_roundtrip(args.op_name, op_args, args.dwg_path, args.out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return int(result.get("exit_code", 2))


if __name__ == "__main__":
    sys.exit(main())
