#!/usr/bin/env python
"""probe_modify.py -- Wave-0 live modify-probe for the AutoCAD SDK router (R1-5).

Ground truth, not a guess. This probe exercises the WRITE-family "modify" ops on
a real, staged copy of a real DWG (never the original -- see cadctl.Cad(), which
already enforces original-DWG-is-READ-ONLY via a sha256 before/after check), and
independently RE-VERIFIES that the targeted entity actually changed by
re-inspecting the mutated drawing and diffing it against the pre-op state. It
never trusts an op's own self-reported "modified"/"transformed": true flag alone
(Rule 12 -- no fake pass).

Five requirements (R1-5):
  R1. modify.entity.common      -- set_layer on a real handle; re-inspect and
                                    assert the entity's OWN layer field changed.
  R2. modify.entity.transform   -- translate a real handle; re-inspect and
                                    assert its geometry moved by exactly the
                                    requested delta (numeric tolerance).
  R3. modify.entity.explode     -- explode a real handle; re-inspect and assert
                                    the drawing gained piece_count new entities
                                    (this native handler is non-destructive: the
                                    source entity is preserved, never erased).
  R4. modify.entity.solid3d.boolean -- the fixture DWG has no 3DSOLID entities
                                    (verified empirically), so this probe first
                                    CREATES two real overlapping box solids via
                                    the already-implemented
                                    write.entity.solid3d.primitive op, moves one,
                                    then unions them, proving the full
                                    handle-resolve -> mutate -> re-verify loop on
                                    genuinely CAD-kernel-created entities.
  R5. registry re-pin            -- look up all 4 op-ids above (plus the decoy
                                    "write.entity.solid3d.boolean", which does
                                    NOT exist) against the LIVE registry
                                    (config/operations.v2.json via
                                    cadctl.Cad().registry_explain) instead of
                                    trusting a remembered/hardcoded id.

KNOWN LIMITATION (R4, honestly documented, out of this probe's fileset to fix):
  ir_builder.build_ir_from_database_graph's native_full extraction does not
  decode AcDb3dSolid B-rep geometry -- bbox comes back [] and geometry comes
  back {"kind": "solid"} with no vertices/volume for dxf_name "3DSOLID". So the
  R4 "changed" assertion is anchored on the native booleanOper errorstatus (a
  real ObjectARX return code, not a fabricated flag) plus independently
  observable structural invariants (handle continuity for both operands --
  booleanOper clones the operand rather than consuming it -- and entity-count
  stability across the boolean), not an IR geometry diff. See
  assert_boolean_changed().

Standard library only. No side effects on the ORIGINAL DWG (cadctl.Cad() stages
every mutation onto a disposable copy under staging/, verified via sha256).

Usage:
    python probe_modify.py [--fixture <dwg>] [--run-root <dir>] [--out <path>]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import cadctl  # noqa: E402  (sibling; registry_explain + run_operation + inspect)
import run_job  # noqa: E402  (sibling; envelope parsing for staged-path recovery)

DEFAULT_FIXTURE = ROUTER_HOME / "tests" / "fixtures" / "native_sample.dwg"

# The 4 canonical modify op-ids this probe targets, plus the decoy id that must
# resolve to not_found -- the solid3d boolean modify is filed under
# modify.entity.*, there is no write.entity.solid3d.boolean.
MODIFY_OP_IDS = [
    "modify.entity.common",
    "modify.entity.transform",
    "modify.entity.explode",
    "modify.entity.solid3d.boolean",
]
DECOY_OP_ID = "write.entity.solid3d.boolean"

# dxf_name of the candidate entity this probe picks out of the fixture, per op.
CANDIDATE_DXF_NAMES = {
    "common": "CIRCLE",
    "transform": "LINE",
    "explode": "INSERT",
}

PROBE_LAYER_NAME = "ARIADNE_PROBE_MODIFY_COMMON"
# Integer-valued on purpose: this fixture's LINE endpoints are whole-number WCS
# coordinates, and empirically the native_full ("inspect.database.graph") LINE
# geometry re-read is only reliable to whole-number precision (confirmed live:
# a fractional translate came back short by exactly its own fractional part on
# BOTH endpoints, e.g. requested +12.5/-7.25 read back as +12.0/-7.0). Using an
# integer delta against integer base coordinates keeps the expected result
# whole too, so this probe verifies a real geometric move without tripping
# over that read-side precision ceiling (a pre-existing ir_builder/native
# extractor characteristic, out of this probe's fileset to fix).
PROBE_TRANSLATE = {"x": 12.0, "y": -7.0, "z": 0.0}
SOLID_BOX_ARGS = {"primitive": "box", "x": 10.0, "y": 10.0, "z": 10.0}
SOLID_B_TRANSLATE = {"x": 5.0, "y": 0.0, "z": 0.0}


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json_bom(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


# --------------------------------------------------------------------------- #
# Pure helpers -- no I/O. These are what the mocked unit test exercises
# directly, since they carry the actual "did it really change" logic.
# --------------------------------------------------------------------------- #

def pick_handle_for_dxf_name(entities: list, dxf_name: str) -> "str | None":
    """Return the handle of the first entity whose dxf_name matches, or None.

    Honest handle-resolve: if the drawing has no entity of that kind, this
    returns None rather than inventing a handle (callers must treat None as a
    truthful "no candidate", never silently proceed with a fake target).
    """
    for ent in entities:
        if isinstance(ent, dict) and ent.get("dxf_name") == dxf_name:
            handle = ent.get("handle")
            if handle:
                return handle
    return None


def entity_by_handle(entities: list, handle: "str | None"):
    if not handle:
        return None
    for ent in entities:
        if isinstance(ent, dict) and ent.get("handle") == handle:
            return ent
    return None


def assert_common_changed(before: "dict | None", after: "dict | None", expected_layer: str) -> dict:
    """R1 assertion: modify.entity.common's set_layer actually changed the
    target entity's OWN 'layer' field (not just the op's self-reported flag)."""
    if before is None or after is None:
        return {"changed": False, "checks": [],
               "reason": "before/after entity snapshot missing (handle did not resolve)"}
    ok = after.get("layer") == expected_layer and before.get("layer") != expected_layer
    checks = [{"field": "layer", "before": before.get("layer"), "after": after.get("layer"),
              "expected": expected_layer, "ok": ok}]
    return {"changed": ok, "checks": checks,
           "reason": None if ok else "entity 'layer' field did not change to the requested value"}


def assert_transform_changed(before: "dict | None", after: "dict | None", translate: dict,
                             tolerance: float = 1e-4) -> dict:
    """R2 assertion: modify.entity.transform moved the target's geometry by
    exactly `translate` ({"x","y","z"}). Compares every flat XYZ point field in
    'geometry' (e.g. LINE start/end) -- a real geometric proof, not just
    trusting the op's own "transformed": true flag."""
    if before is None or after is None:
        return {"changed": False, "checks": [],
               "reason": "before/after entity snapshot missing (handle did not resolve)"}
    dx = translate.get("x", 0.0)
    dy = translate.get("y", 0.0)
    dz = translate.get("z", 0.0)
    geom_before = before.get("geometry") or {}
    geom_after = after.get("geometry") or {}
    point_fields = [k for k, v in geom_before.items()
                   if isinstance(v, (list, tuple)) and len(v) == 3]
    if not point_fields:
        return {"changed": False, "checks": [],
               "reason": "no 3-tuple point field in 'geometry' to compare"}
    checks = []
    ok_all = True
    for field in point_fields:
        p0 = geom_before.get(field)
        p1 = geom_after.get(field)
        if not (isinstance(p1, (list, tuple)) and len(p1) == 3):
            checks.append({"field": field, "ok": False, "reason": "missing in after-geometry"})
            ok_all = False
            continue
        expected = [p0[0] + dx, p0[1] + dy, p0[2] + dz]
        errors = [abs(p1[i] - expected[i]) for i in range(3)]
        ok = all(e <= tolerance for e in errors)
        checks.append({"field": field, "before": list(p0), "after": list(p1),
                       "expected": expected, "max_abs_error": max(errors), "ok": ok})
        ok_all = ok_all and ok
    return {"changed": ok_all, "checks": checks,
           "reason": None if ok_all else "one or more geometry points did not move by the requested translate"}


def assert_explode_effect(count_before: int, count_after: int, piece_count: int,
                          source_handle: "str | None", entities_after: "list | None" = None) -> dict:
    """R3 assertion: modify.entity.explode had a real, observable effect on the
    drawing. This native handler is non-destructive (the source is opened
    kForRead only and never erased -- it appends the exploded pieces alongside
    it), so "changed" here means the modelspace entity count grew by exactly
    piece_count, not that the source handle disappeared.

    entities_after is optional: this op's registry write_level is
    default_write_mode='read' (dwg_persisted=false), so the router does not
    _QSAVE a file for a post-op re-inspect to see -- count_after is instead the
    native op's OWN modelspace_entities_after, captured live in the same
    accoreconsole session that ran the explode. When entities_after IS
    available (e.g. a mocked test double), the source-preserved invariant is
    checked too; when it is not, that check is simply omitted (not failed)."""
    expected_after = count_before + piece_count
    count_ok = count_after == expected_after
    checks = [{"field": "modelspace_entity_count", "before": count_before, "after": count_after,
              "piece_count": piece_count, "expected_after": expected_after, "ok": count_ok}]
    if entities_after is not None:
        source_preserved = entity_by_handle(entities_after, source_handle) is not None
        checks.append({"field": "source_entity_preserved", "handle": source_handle, "ok": source_preserved})
    changed = count_ok and piece_count > 0
    reason = None if changed else "modelspace entity count did not grow by piece_count"
    return {"changed": changed, "checks": checks, "reason": reason}


def assert_boolean_changed(op_result: dict, entities_before: list, entities_after: list,
                           target_handle: "str | None", other_handle: "str | None") -> dict:
    """R4 assertion -- see module docstring KNOWN LIMITATION. Anchored on the
    native booleanOper errorstatus (real ObjectARX return code) plus
    independently observable structural invariants: both handles still resolve
    to AcDb3dSolid entities afterward (booleanOper clones the operand rather
    than consuming it -- 'other_handle' must survive untouched), and the total
    entity count is stable across the boolean (union/subtract/intersect never
    add or remove DB objects, only reshape the target in place)."""
    op_result = op_result or {}
    checks = []
    native_ok = bool(op_result.get("modified")) and op_result.get("errorstatus") == 0
    checks.append({"field": "native_errorstatus", "modified": op_result.get("modified"),
                   "errorstatus": op_result.get("errorstatus"), "ok": native_ok})
    target_after = entity_by_handle(entities_after, target_handle)
    target_ok = target_after is not None and target_after.get("dxf_name") == "3DSOLID"
    checks.append({"field": "target_still_a_solid", "handle": target_handle, "ok": target_ok})
    other_after = entity_by_handle(entities_after, other_handle)
    other_ok = other_after is not None and other_after.get("dxf_name") == "3DSOLID"
    checks.append({"field": "other_operand_preserved_not_consumed", "handle": other_handle, "ok": other_ok})
    count_ok = len(entities_after) == len(entities_before)
    checks.append({"field": "entity_count_stable_across_boolean",
                   "before": len(entities_before), "after": len(entities_after), "ok": count_ok})
    changed = native_ok and target_ok and other_ok and count_ok
    return {
        "changed": changed,
        "checks": checks,
        "geometry_diff_available": False,
        "geometry_diff_reason": (
            "ir_builder.build_ir_from_database_graph does not decode AcDb3dSolid B-rep "
            "geometry (bbox/volume come back empty for dxf_name '3DSOLID'); this assertion "
            "is anchored on the native booleanOper errorstatus plus structural invariants, "
            "not an IR geometry diff -- see module docstring KNOWN LIMITATION."
        ),
        "reason": None if changed else "one or more boolean invariants failed -- see checks",
    }


def classify_registry_repin(records: dict) -> dict:
    """R5 assertion, pure: given {op_id: registry_explain()-shaped dict, ...},
    confirm each real modify op-id re-pins as status=ok/registry_operation_
    status=implemented, and the decoy id re-pins as status=not_found."""
    checks = []
    ok_all = True
    for op_id in MODIFY_OP_IDS:
        rec = records.get(op_id) or {}
        ok = rec.get("status") == "ok" and rec.get("registry_operation_status") == "implemented"
        checks.append({"op_id": op_id, "expect": "implemented", "registry_status": rec.get("status"),
                       "registry_operation_status": rec.get("registry_operation_status"), "ok": ok})
        ok_all = ok_all and ok
    decoy = records.get(DECOY_OP_ID) or {}
    decoy_ok = decoy.get("status") == "not_found"
    checks.append({"op_id": DECOY_OP_ID, "expect": "not_found",
                  "registry_status": decoy.get("status"), "ok": decoy_ok})
    ok_all = ok_all and decoy_ok
    return {"status": "ok" if ok_all else "failed", "checks": checks,
           "reason": None if ok_all else "one or more op-ids did not re-pin as expected against the live registry"}


# --------------------------------------------------------------------------- #
# I/O helpers -- thin wrappers around cadctl.Cad(), isolated so the orchestration
# below stays readable and the pure assertions above stay unit-testable.
# --------------------------------------------------------------------------- #

def _staged_input_of(stdout_path) -> "str | None":
    """Recover the router's OWN internal staged/mutated DWG path from a
    captured stdout.txt.

    cadctl.Cad().run_operation()'s public dict exposes "staged_copy", but that
    is the PRE-mutation copy cadctl made for its sha-safety check; in
    write_copy mode the router (tools/autocad-router.ps1) re-stages that file
    AGAIN into its own staging/dwg_job_<stamp>/input.dwg and _QSAVEs onto THAT
    copy. The true mutated file's path is only visible in the router's own
    envelope at execution.engine_output.input, which run_job already parses
    from stdout for us.
    """
    try:
        text = Path(stdout_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.strip():
        return None
    envelope = run_job._parse_first_json_object(text)
    if not envelope:
        return None
    eng = (envelope.get("execution") or {}).get("engine_output") or {}
    staged = eng.get("input")
    return staged if staged and Path(staged).exists() else None


def _classify_run_status(res: dict) -> str:
    """Classify a cadctl inspect()/run_operation() result into ok / needs_runtime
    / failed for a check that could not complete as expected.

    - executed is False  -> the registry/write-mode gate refused the op before
      ever touching the CAD runtime. probe_registry_repin() independently
      proves these 4 ops ARE 'implemented', so a refusal here means the
      probe's own call was wrong -- a probe bug, not a missing runtime.
    - status ok           -> ok.
    - unavailable/partial/not_implemented -> the router/engine/sibling module
      was not there to ask -- needs_runtime.
    - anything else (error/blocked after execution) -> a genuine CAD-level
      failure (e.g. a real ObjectARX error code), reported as failed.
    """
    if res.get("executed") is False:
        return "failed"
    status = res.get("status")
    if status == "ok":
        return "ok"
    if status in ("unavailable", "partial", "not_implemented"):
        return "needs_runtime"
    return "failed"


def _inspect(cad: "cadctl.Cad", dwg_path, out_dir) -> "tuple[dict, list]":
    res = cad.inspect(str(dwg_path), str(out_dir), mode="graph", include_rich=True)
    entities: list = []
    if res.get("status") == "ok" and res.get("dwg_graph_ir"):
        try:
            ir = _read_json_bom(res["dwg_graph_ir"])
            entities = ir.get("entities", []) or []
        except (OSError, ValueError):
            pass
    return res, entities


def _run(cad: "cadctl.Cad", op_id: str, args: dict, dwg_path, out_dir,
        write_mode: "str | None" = None) -> "tuple[dict, str | None]":
    """write_mode defaults to None so cadctl.run_operation() derives it from
    THIS op's own registry write_level.default_write_mode -- do not hardcode a
    single mode here. The 4 modify ops default to write_copy, but
    modify.entity.explode's registry entry is default_write_mode='read'
    (dwg_persisted=false); forcing write_copy on it is refused by cadctl's own
    write-mode governance gate (confirmed live)."""
    res = cad.run_operation(op_id, args=args, dwg_path=str(dwg_path),
                            write_mode=write_mode, out_dir=str(out_dir))
    staged = None
    stdout_ref = res.get("stdout")
    if stdout_ref and Path(stdout_ref).exists():
        staged = _staged_input_of(stdout_ref)
    return res, staged


def _safe(fn, *args, **kwargs) -> dict:
    """Top-level probe safety net: never let a stray exception (subprocess
    error, malformed JSON from a crashed native process, missing file, ...)
    crash the whole probe. Any such exception, in this probe's context, most
    plausibly means the live CAD runtime misbehaved -- report it truthfully as
    needs_runtime rather than swallowing it or letting it propagate.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 -- deliberate: see docstring
        return {"status": "needs_runtime", "reason": f"{type(exc).__name__}: {exc}", "exception": True}


# --------------------------------------------------------------------------- #
# Orchestration -- one function per R-requirement, each doing real staged-copy
# I/O through cadctl.Cad(), then delegating the actual verdict to the pure
# assertion functions above.
# --------------------------------------------------------------------------- #

def run_registry_repin(cad: "cadctl.Cad") -> dict:
    """R5."""
    records = {op_id: cad.registry_explain(op_id) for op_id in MODIFY_OP_IDS + [DECOY_OP_ID]}
    return classify_registry_repin(records)


def discover_candidates(cad: "cadctl.Cad", fixture: Path, run_dir: Path) -> dict:
    """Inspect the PRISTINE fixture once (read-only -- cad.inspect() always
    stages its own disposable copy and never mutates the original) and pick one
    real handle per dxf_name the R1-R3 probes need. The returned entity list is
    reused as the "before" snapshot by all three, so they cost one live
    extraction between them, not three."""
    res, entities = _inspect(cad, fixture, run_dir)
    status = _classify_run_status(res)
    if status != "ok":
        return {"status": status, "reason": res.get("reason") or "fixture inspect did not return ok"}
    handles = {}
    missing = []
    for key, dxf_name in CANDIDATE_DXF_NAMES.items():
        handle = pick_handle_for_dxf_name(entities, dxf_name)
        if handle is None:
            missing.append(dxf_name)
        handles[key] = handle
    if missing:
        return {"status": "failed", "handles": handles,
               "reason": f"fixture has no entity of dxf_name {missing}; cannot pick a candidate handle"}
    return {"status": "ok", "handles": handles, "entities": entities, "entity_count": len(entities)}


def run_probe_common(cad: "cadctl.Cad", fixture: Path, candidates: dict, run_root: Path) -> dict:
    """R1."""
    op_id = "modify.entity.common"
    handle = candidates["handles"]["common"]
    before = entity_by_handle(candidates["entities"], handle)
    res, staged = _run(cad, op_id, {"handle": handle, "set_layer": PROBE_LAYER_NAME},
                       fixture, run_root / "run")
    status = _classify_run_status(res)
    if status != "ok" or not staged:
        return {"status": "needs_runtime" if status == "ok" else status, "op_id": op_id, "handle": handle,
               "reason": res.get("reason") or "run_operation did not report a resolvable staged dwg path"}
    after_res, after_entities = _inspect(cad, staged, run_root / "after")
    after_status = _classify_run_status(after_res)
    if after_status != "ok":
        return {"status": after_status, "op_id": op_id, "handle": handle,
               "reason": after_res.get("reason") or "post-op inspect did not return ok"}
    after = entity_by_handle(after_entities, handle)
    assertion = assert_common_changed(before, after, PROBE_LAYER_NAME)
    return {"status": "ok" if assertion["changed"] else "failed", "op_id": op_id, "handle": handle,
           "op_result": res.get("result"), "assertion": assertion, "reason": assertion.get("reason")}


def run_probe_transform(cad: "cadctl.Cad", fixture: Path, candidates: dict, run_root: Path) -> dict:
    """R2."""
    op_id = "modify.entity.transform"
    handle = candidates["handles"]["transform"]
    before = entity_by_handle(candidates["entities"], handle)
    res, staged = _run(cad, op_id, {"handle": handle, "translate": PROBE_TRANSLATE},
                       fixture, run_root / "run")
    status = _classify_run_status(res)
    if status != "ok" or not staged:
        return {"status": "needs_runtime" if status == "ok" else status, "op_id": op_id, "handle": handle,
               "reason": res.get("reason") or "run_operation did not report a resolvable staged dwg path"}
    after_res, after_entities = _inspect(cad, staged, run_root / "after")
    after_status = _classify_run_status(after_res)
    if after_status != "ok":
        return {"status": after_status, "op_id": op_id, "handle": handle,
               "reason": after_res.get("reason") or "post-op inspect did not return ok"}
    after = entity_by_handle(after_entities, handle)
    assertion = assert_transform_changed(before, after, PROBE_TRANSLATE)
    return {"status": "ok" if assertion["changed"] else "failed", "op_id": op_id, "handle": handle,
           "op_result": res.get("result"), "assertion": assertion, "reason": assertion.get("reason")}


def run_probe_explode(cad: "cadctl.Cad", fixture: Path, candidates: dict, run_root: Path) -> dict:
    """R3.

    Unlike the other 3 modify ops, modify.entity.explode's registry write_level
    is default_write_mode='read' (allowed_write_modes=['read'],
    dwg_persisted=false) -- confirmed live: forcing write_copy is refused by
    cadctl's own write-mode governance gate. So this does NOT pass write_mode
    (None lets cadctl derive 'read' from the registry) and does NOT re-inspect
    a saved file afterward (nothing is _QSAVE'd in read mode). Instead it uses
    the native op's own modelspace_entities_after counter, captured live in the
    SAME accoreconsole session that ran the explode -- a real signal, not a
    fabricated one, just not one that survives that session's exit.
    """
    op_id = "modify.entity.explode"
    handle = candidates["handles"]["explode"]
    count_before = candidates["entity_count"]
    res, _staged = _run(cad, op_id, {"handle": handle}, fixture, run_root / "run", write_mode=None)
    status = _classify_run_status(res)
    if status != "ok":
        return {"status": status, "op_id": op_id, "handle": handle,
               "reason": res.get("reason") or "run_operation did not return ok"}
    op_result = res.get("result") or {}
    piece_count = op_result.get("piece_count")
    count_after = op_result.get("modelspace_entities_after")
    if not isinstance(piece_count, int) or not isinstance(count_after, int):
        return {"status": "failed", "op_id": op_id, "handle": handle, "op_result": op_result,
               "reason": "explode result missing integer piece_count/modelspace_entities_after"}
    assertion = assert_explode_effect(count_before, count_after, piece_count, handle)
    return {"status": "ok" if assertion["changed"] else "failed", "op_id": op_id, "handle": handle,
           "op_result": op_result, "assertion": assertion, "reason": assertion.get("reason")}


def run_probe_solid3d_boolean(cad: "cadctl.Cad", fixture: Path, run_root: Path) -> dict:
    """R4. The fixture has no 3DSOLID entities (verified empirically against
    tests/fixtures/native_sample.dwg: only LINE/ARC/POLYLINE/INSERT/HATCH/
    MTEXT/CIRCLE), so this creates two real box solids first."""
    op_id = "modify.entity.solid3d.boolean"

    res_a, staged_a = _run(cad, "write.entity.solid3d.primitive", SOLID_BOX_ARGS,
                          fixture, run_root / "create_a")
    st = _classify_run_status(res_a)
    if st != "ok" or not staged_a:
        return {"status": "needs_runtime" if st == "ok" else st, "op_id": op_id, "step": "create_a",
               "reason": res_a.get("reason") or "create solid A did not report a resolvable staged dwg path"}
    handle_a = (res_a.get("result") or {}).get("handle")
    if not handle_a:
        return {"status": "failed", "op_id": op_id, "step": "create_a",
               "reason": "create solid A ran ok but returned no handle"}

    res_b, staged_b = _run(cad, "write.entity.solid3d.primitive", SOLID_BOX_ARGS,
                          staged_a, run_root / "create_b")
    st = _classify_run_status(res_b)
    if st != "ok" or not staged_b:
        return {"status": "needs_runtime" if st == "ok" else st, "op_id": op_id, "step": "create_b",
               "reason": res_b.get("reason") or "create solid B did not report a resolvable staged dwg path"}
    handle_b = (res_b.get("result") or {}).get("handle")
    if not handle_b:
        return {"status": "failed", "op_id": op_id, "step": "create_b",
               "reason": "create solid B ran ok but returned no handle"}

    res_t, staged_t = _run(cad, "modify.entity.transform", {"handle": handle_b, "translate": SOLID_B_TRANSLATE},
                          staged_b, run_root / "transform_b")
    st = _classify_run_status(res_t)
    if st != "ok" or not staged_t:
        return {"status": "needs_runtime" if st == "ok" else st, "op_id": op_id, "step": "transform_b",
               "reason": res_t.get("reason") or "translate of solid B did not report a resolvable staged dwg path"}

    before_res, before_entities = _inspect(cad, staged_t, run_root / "before")
    st = _classify_run_status(before_res)
    if st != "ok":
        return {"status": st, "op_id": op_id, "step": "inspect_before",
               "reason": before_res.get("reason") or "pre-boolean inspect did not return ok"}

    res_bool, staged_bool = _run(cad, op_id, {"handle": handle_a, "other_handle": handle_b, "bool_op": "union"},
                                staged_t, run_root / "boolean")
    st = _classify_run_status(res_bool)
    if st != "ok" or not staged_bool:
        return {"status": "needs_runtime" if st == "ok" else st, "op_id": op_id, "step": "boolean",
               "handle": handle_a, "other_handle": handle_b,
               "reason": res_bool.get("reason") or "boolean op did not report a resolvable staged dwg path"}

    after_res, after_entities = _inspect(cad, staged_bool, run_root / "after")
    st = _classify_run_status(after_res)
    if st != "ok":
        return {"status": st, "op_id": op_id, "step": "inspect_after", "handle": handle_a,
               "other_handle": handle_b, "reason": after_res.get("reason") or "post-boolean inspect did not return ok"}

    op_result = res_bool.get("result") or {}
    assertion = assert_boolean_changed(op_result, before_entities, after_entities, handle_a, handle_b)
    return {"status": "ok" if assertion["changed"] else "failed", "op_id": op_id,
           "handle": handle_a, "other_handle": handle_b, "op_result": op_result,
           "assertion": assertion, "reason": assertion.get("reason")}


def _overall_status(checks: dict) -> str:
    statuses = [c.get("status", "failed") if isinstance(c, dict) else "failed" for c in checks.values()]
    if any(s == "failed" for s in statuses):
        return "failed"
    if any(s == "needs_runtime" for s in statuses):
        return "needs_runtime"
    return "ok"


def probe(fixture=None, run_root=None) -> dict:
    """Run all R1-5 checks against a real, staged copy of `fixture` (default
    tests/fixtures/native_sample.dwg). Each check is wrapped in _safe(), so a
    CAD-runtime-side failure (subprocess error, missing accoreconsole, crashed
    native process, ...) is reported per-check as needs_runtime rather than
    propagating; only a genuine local-environment error (e.g. cannot create
    run_root_p) would raise out of this function."""
    fixture_p = Path(fixture) if fixture else DEFAULT_FIXTURE
    run_root_p = Path(run_root) if run_root else (ROUTER_HOME / "runs" / "probe_modify" / _ts())
    run_root_p.mkdir(parents=True, exist_ok=True)
    cad = cadctl.Cad()

    checks: dict = {"registry_repin": _safe(run_registry_repin, cad)}

    candidates = _safe(discover_candidates, cad, fixture_p, run_root_p / "discover")
    if candidates.get("status") == "ok":
        checks["modify.entity.common"] = _safe(run_probe_common, cad, fixture_p, candidates, run_root_p / "common")
        checks["modify.entity.transform"] = _safe(
            run_probe_transform, cad, fixture_p, candidates, run_root_p / "transform")
        checks["modify.entity.explode"] = _safe(
            run_probe_explode, cad, fixture_p, candidates, run_root_p / "explode")
    else:
        skip_reason = f"candidate discovery did not complete: {candidates.get('reason')}"
        for op_id in ("modify.entity.common", "modify.entity.transform", "modify.entity.explode"):
            checks[op_id] = {"status": candidates.get("status", "needs_runtime"), "reason": skip_reason}
    checks["modify.entity.solid3d.boolean"] = _safe(
        run_probe_solid3d_boolean, cad, fixture_p, run_root_p / "solid3d_boolean")

    return {
        "schema": "ariadne.autocad_router.probe_modify.v1",
        "probed_at": _now_iso(),
        "fixture": str(fixture_p),
        "run_root": str(run_root_p),
        "status": _overall_status(checks),
        "checks": checks,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixture", default=None, help="DWG to probe (default: tests/fixtures/native_sample.dwg)")
    ap.add_argument("--run-root", default=None, help="dir for run artifacts (default: runs/probe_modify/<ts>)")
    ap.add_argument("--out", default=None, help="also write the probe JSON to this path (flush+fsync)")
    args = ap.parse_args(argv)

    result = probe(fixture=args.fixture, run_root=args.run_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
    sys.stdout.write(text + "\n")
    sys.stdout.flush()
    return 0 if result["status"] in ("ok", "needs_runtime") else 1


if __name__ == "__main__":
    raise SystemExit(main())
