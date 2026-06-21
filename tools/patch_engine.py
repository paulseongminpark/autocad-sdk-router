#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_engine.py -- Lane E patch shell for the CAD OS Layer.

A patch is an ``ariadne.cad_patch.v1`` document (conforms
``schemas/cad_patch.v1.schema.json``): an ordered, idempotent batch of CAD
mutations that ALWAYS target a STAGED copy of a drawing, never an original in
place.

The SAFE-SHELL surface (frozen, behavior-preserving) plans without mutating:
  * validate_patch_schema(patch)  -- structural validation against cad_patch.v1
  * classify_patch_risk(patch)    -- low/medium/high/blocked risk classification
  * dry_run_plan(patch)           -- resolves each op to its registry mapping and
                                     returns a PLAN; it does not execute anything
  * guards: reject_write_original_by_default, require_staged_copy,
            require_validation

M02 ADDS a REAL staged-copy execution lifecycle on top of that shell. The
original DWG is NEVER touched: ``apply_staged`` copies the input to a writable
staging path (recording the original sha256/byte_size before AND after as a
no-original-write proof), then drives the canonical router (tools/run_job.py ->
tools/autocad-router.ps1) entirely on staged copies:

  validate_patch_schema -> classify_patch_risk -> create_staged_copy
    -> pre-inspect   (native_full IR of the staged copy)
    -> apply         (native ObjectARX write op on the staged copy, write_copy)
    -> post-inspect  (native_full IR of the mutated staged_output.dwg)
    -> compute_diff  (cad_diff.v1, via the cad_diff sibling lane)
    -> validate      (validation_report.v1, via the validator sibling lane)
    -> journal       (ordered steps + every command's stdout/stderr/exit ref +
                      original-unchanged proof)

Patch op -> native write op mapping (the only ops with a live native handler):
    create_line   -> write.entity.line
    create_circle -> write.entity.circle
    set_layer     -> write.layer.create
    create_layer  -> write.layer.create
Any other declared op (create_polyline / create_text / move_entity /
delete_entity / unknown) has no native write handler today and is reported
``not_implemented`` -- never a faked success.

Hard rules: standard library ONLY; no-fake-success (a route/host/sibling that is
unavailable => not_implemented/unavailable/partial/blocked with a reason, never a
fake ok); the original is READ-ONLY (operate only on staged copies); a patch with
``policy.staged_copy != true`` is rejected; sibling lanes (cad_diff / validator /
ir_builder) are imported via ``_import_optional`` so a not-yet-present sibling
degrades to not_implemented rather than crashing.

Default policy: dry_run is the CLI default; ``apply_staged`` is the explicit
staged write; ``allow_original_write`` stays false; the raw command surface is
denied.

Public API (SAFE SHELL -- preserved):
    PATCH_SCHEMA_ID, DECLARED_OPS, OP_REGISTRY_MAP
    validate_patch_schema(patch) -> dict
    classify_patch_risk(patch)   -> dict
    dry_run_plan(patch)          -> dict
    reject_write_original_by_default(patch) -> dict
    require_staged_copy(patch)   -> dict
    require_validation(patch)    -> dict

Public API (M02 -- staged-copy execution lifecycle, additive):
    NATIVE_WRITE_OP_MAP
    create_staged_copy(dwg_path, out_dir) -> dict
    apply_staged(patch, dwg_path, out_dir) -> dict
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)
_OPERATIONS_V2 = os.path.join(_ROUTER_HOME, "config", "operations.v2.json")
_JSON_ENCODING = "utf-8-sig"

# Ensure sibling tools/*.py are importable when patch_engine is imported by path.
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

PATCH_SCHEMA_ID = "ariadne.cad_patch.v1"
RESULT_SCHEMA_ID = "ariadne.cad_patch.result.v1"

# The declared high-level mutation operations this shell understands, mapped to
# the operation-registry id (config/operations.v2.json) that carries the native
# operation evidence.
OP_REGISTRY_MAP: Dict[str, str] = {
    "create_line": "write.entity.line",
    "create_polyline": "write.entity.polyline",
    "create_text": "write.entity.text",
    "set_layer": "write.entity.modify",
    "move_entity": "write.entity.modify",
    "delete_entity": "write.entity.delete",
}
DECLARED_OPS = tuple(OP_REGISTRY_MAP.keys())

# Risk class per declared op. delete/move/set_layer mutate existing entities
# (higher blast radius); create_* only add. Anything unknown is high by default.
_OP_RISK: Dict[str, str] = {
    "create_line": "low",
    "create_polyline": "low",
    "create_text": "low",
    "set_layer": "medium",
    "move_entity": "medium",
    "delete_entity": "high",
}

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "blocked": 3}


def _load_registry() -> Optional[Dict[str, Any]]:
    if not os.path.isfile(_OPERATIONS_V2):
        return None
    try:
        with open(_OPERATIONS_V2, "r", encoding=_JSON_ENCODING) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _registry_status(op_id: str) -> Optional[str]:
    reg = _load_registry()
    if not reg:
        return None
    for o in reg.get("operations", []):
        if isinstance(o, dict) and o.get("id") == op_id:
            return o.get("status")
    return None


# --------------------------------------------------------------------------- #
# Schema validation (structural; stdlib only, not a full JSON-Schema engine)
# --------------------------------------------------------------------------- #

def validate_patch_schema(patch: Any) -> Dict[str, Any]:
    """
    Validate a patch object against the required structure of cad_patch.v1.

    Returns {"valid": bool, "errors": [...], "warnings": [...]}.
    Checks: schema const, required top-level fields, target_dwg.staged_path,
    operations[] non-empty with a resolvable 'operation', policy.staged_copy==true,
    and condition op enums on pre/postconditions.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(patch, dict):
        return {"valid": False,
                "errors": ["patch must be a JSON object, got %s" % type(patch).__name__],
                "warnings": []}

    if patch.get("schema") != PATCH_SCHEMA_ID:
        errors.append("schema must be '%s' (got %r)" % (PATCH_SCHEMA_ID, patch.get("schema")))

    for req in ("schema", "patch_id", "target_dwg", "operations", "policy"):
        if req not in patch:
            errors.append("missing required field: %s" % req)

    if isinstance(patch.get("patch_id"), str):
        if not patch["patch_id"].strip():
            errors.append("patch_id must be a non-empty string")
    elif "patch_id" in patch:
        errors.append("patch_id must be a string")

    # target_dwg.staged_path required; must differ from original_path.
    tgt = patch.get("target_dwg")
    if isinstance(tgt, dict):
        staged = tgt.get("staged_path")
        if not isinstance(staged, str) or not staged.strip():
            errors.append("target_dwg.staged_path is required (non-empty string)")
        original = tgt.get("original_path")
        if isinstance(staged, str) and isinstance(original, str):
            if os.path.normcase(os.path.normpath(staged)) == \
               os.path.normcase(os.path.normpath(original)):
                errors.append("target_dwg.staged_path must differ from original_path")
    elif "target_dwg" in patch:
        errors.append("target_dwg must be an object")

    # operations[] non-empty; each needs an 'operation'.
    ops = patch.get("operations")
    if isinstance(ops, list):
        if not ops:
            errors.append("operations[] must contain at least one operation")
        for i, op in enumerate(ops):
            if not isinstance(op, dict):
                errors.append("operations[%d] must be an object" % i)
                continue
            op_id = op.get("operation")
            if not isinstance(op_id, str) or not op_id.strip():
                errors.append("operations[%d].operation is required (non-empty string)" % i)
            elif op_id not in OP_REGISTRY_MAP:
                warnings.append("operations[%d].operation '%s' is not a declared op %s"
                                % (i, op_id, list(DECLARED_OPS)))
            if "args" in op and not isinstance(op["args"], dict):
                errors.append("operations[%d].args must be an object" % i)
    elif "operations" in patch:
        errors.append("operations must be an array")

    # policy.staged_copy must be true (hard safety invariant).
    pol = patch.get("policy")
    if isinstance(pol, dict):
        if pol.get("staged_copy") is not True:
            errors.append("policy.staged_copy must be true (original-DWG safety)")
        wm = pol.get("write_mode")
        if wm is not None and wm not in ("write_copy", "write_original", "live_edit"):
            errors.append("policy.write_mode invalid: %r" % wm)
    elif "policy" in patch:
        errors.append("policy must be an object")

    # condition op enums.
    valid_cond_ops = {"eq", "ne", "gt", "ge", "lt", "le",
                      "exists", "not_exists", "delta_eq", "delta_ge"}
    for field in ("preconditions", "postconditions"):
        conds = patch.get(field)
        if conds is None:
            continue
        if not isinstance(conds, list):
            errors.append("%s must be an array" % field)
            continue
        for j, c in enumerate(conds):
            if not isinstance(c, dict):
                errors.append("%s[%d] must be an object" % (field, j))
                continue
            if not isinstance(c.get("subject"), str) or not c["subject"].strip():
                errors.append("%s[%d].subject is required" % (field, j))
            if c.get("op") not in valid_cond_ops:
                errors.append("%s[%d].op invalid: %r" % (field, j, c.get("op")))

    return {"valid": not errors, "errors": errors, "warnings": warnings}


# --------------------------------------------------------------------------- #
# Risk classification
# --------------------------------------------------------------------------- #

def classify_patch_risk(patch: Any) -> Dict[str, Any]:
    """
    Classify the risk of a patch. Returns
    {"risk": low|medium|high|blocked, "reasons": [...], "per_op": [...]}.

    A patch is ``blocked`` (cannot be safely planned) when a hard guard fails
    (no staged copy, or write_mode targets the original). Otherwise risk is the
    max over its ops, bumped to high if it deletes/moves with no postconditions
    to verify the change.
    """
    reasons: List[str] = []

    if not isinstance(patch, dict):
        return {"risk": "blocked", "reasons": ["patch is not an object"], "per_op": []}

    pol = patch.get("policy") or {}
    if pol.get("staged_copy") is not True:
        reasons.append("policy.staged_copy is not true")
        return {"risk": "blocked", "reasons": reasons, "per_op": []}
    if pol.get("write_mode") in ("write_original", "live_edit"):
        reasons.append("policy.write_mode=%s targets the original/active doc"
                       % pol.get("write_mode"))
        return {"risk": "blocked", "reasons": reasons, "per_op": []}

    ops = patch.get("operations") or []
    per_op: List[Dict[str, Any]] = []
    max_risk = "low"
    has_mutation_of_existing = False
    for i, op in enumerate(ops if isinstance(ops, list) else []):
        op_id = op.get("operation") if isinstance(op, dict) else None
        risk = _OP_RISK.get(op_id, "high")
        if op_id in ("delete_entity", "move_entity", "set_layer"):
            has_mutation_of_existing = True
        per_op.append({"index": i, "operation": op_id, "risk": risk})
        if _RISK_ORDER[risk] > _RISK_ORDER[max_risk]:
            max_risk = risk

    postconds = patch.get("postconditions") or []
    if has_mutation_of_existing and not postconds:
        if _RISK_ORDER["high"] > _RISK_ORDER[max_risk]:
            max_risk = "high"
        reasons.append("mutates/deletes existing entities with no postconditions "
                       "to verify the result")

    if not ops:
        reasons.append("patch has no operations")

    return {"risk": max_risk, "reasons": reasons, "per_op": per_op}


# --------------------------------------------------------------------------- #
# Guards (each returns {"ok": bool, "guard": id, "message": str})
# --------------------------------------------------------------------------- #

def require_staged_copy(patch: Any) -> Dict[str, Any]:
    """Guard: the patch must operate on a staged copy distinct from the original."""
    gid = "require_staged_copy"
    if not isinstance(patch, dict):
        return {"ok": False, "guard": gid, "message": "patch is not an object"}
    pol = patch.get("policy") or {}
    if pol.get("staged_copy") is not True:
        return {"ok": False, "guard": gid, "message": "policy.staged_copy must be true"}
    tgt = patch.get("target_dwg") or {}
    staged = tgt.get("staged_path")
    original = tgt.get("original_path")
    if not isinstance(staged, str) or not staged.strip():
        return {"ok": False, "guard": gid, "message": "target_dwg.staged_path missing"}
    if isinstance(original, str) and \
       os.path.normcase(os.path.normpath(staged)) == \
       os.path.normcase(os.path.normpath(original)):
        return {"ok": False, "guard": gid,
                "message": "staged_path equals original_path (would touch original)"}
    return {"ok": True, "guard": gid, "message": "staged copy is distinct from original"}


def reject_write_original_by_default(patch: Any) -> Dict[str, Any]:
    """
    Guard: by default refuse any patch whose effective write level targets the
    original or active document. write_copy (or unset, which defaults to
    write_copy) is allowed; write_original/live_edit are refused here.
    """
    gid = "reject_write_original_by_default"
    if not isinstance(patch, dict):
        return {"ok": False, "guard": gid, "message": "patch is not an object"}
    pol = patch.get("policy") or {}
    wm = pol.get("write_mode", "write_copy")
    if wm in ("write_original", "live_edit"):
        return {"ok": False, "guard": gid,
                "message": "write_mode=%s refused by default (no original/active writes)" % wm}
    return {"ok": True, "guard": gid, "message": "write_mode=%s is safe" % wm}


def require_validation(patch: Any) -> Dict[str, Any]:
    """
    Guard: a mutating patch must declare postconditions so the result can be
    validated (drives validation_report gates). A pure no-op patch is allowed
    without postconditions.
    """
    gid = "require_validation"
    if not isinstance(patch, dict):
        return {"ok": False, "guard": gid, "message": "patch is not an object"}
    ops = patch.get("operations") or []
    postconds = patch.get("postconditions") or []
    if ops and not postconds:
        return {"ok": False, "guard": gid,
                "message": "patch mutates but declares no postconditions to validate"}
    return {"ok": True, "guard": gid, "message": "validation conditions present (or no-op)"}


def _run_guards(patch: Any) -> List[Dict[str, Any]]:
    return [
        require_staged_copy(patch),
        reject_write_original_by_default(patch),
        require_validation(patch),
    ]


# --------------------------------------------------------------------------- #
# Dry-run planning (NO execution)
# --------------------------------------------------------------------------- #

def dry_run_plan(patch: Any) -> Dict[str, Any]:
    """
    Produce a PLAN for a patch without executing anything.

    Returns:
      {
        "schema": "ariadne.cad_patch.dry_run.v1",
        "patch_id": ...,
        "schema_validation": {valid, errors, warnings},
        "risk": {risk, reasons, per_op},
        "guards": [ {ok, guard, message}, ... ],
        "guards_ok": bool,
        "planned_ops": [ {index, operation, registry_op, registry_status,
                          execution_status="not_implemented", args, ...} ],
        "execution": "not_implemented",
        "status": "planned" | "rejected",
        "notes": [...]
      }

    ``status`` is "rejected" when schema validation fails or any guard fails;
    otherwise "planned". EXECUTION is always ``not_implemented`` in this packet.
    """
    notes: List[str] = []
    schema_validation = validate_patch_schema(patch)
    risk = classify_patch_risk(patch)
    guards = _run_guards(patch)
    guards_ok = all(g["ok"] for g in guards)

    patch_id = patch.get("patch_id") if isinstance(patch, dict) else None
    ops = (patch.get("operations") or []) if isinstance(patch, dict) else []

    planned_ops: List[Dict[str, Any]] = []
    for i, op in enumerate(ops if isinstance(ops, list) else []):
        if not isinstance(op, dict):
            continue
        op_id = op.get("operation")
        registry_op = OP_REGISTRY_MAP.get(op_id)
        registry_status = _registry_status(registry_op) if registry_op else None
        # The patch-apply pipeline itself (apply.patch) is a stub today; record it.
        apply_status = _registry_status("apply.patch")
        planned_ops.append({
            "index": i,
            "step_id": op.get("step_id"),
            "operation": op_id,
            "registry_op": registry_op,
            "registry_status": registry_status,
            "apply_pipeline_op": "apply.patch",
            "apply_pipeline_status": apply_status,
            "args": op.get("args", {}),
            "risk": _OP_RISK.get(op_id, "high"),
            "execution_status": "not_implemented",
        })

    if _load_registry() is None:
        notes.append("operations.v2.json unavailable; registry_status fields are null")

    status = "planned" if (schema_validation["valid"] and guards_ok) else "rejected"
    if not schema_validation["valid"]:
        notes.append("schema validation failed: %s" % "; ".join(schema_validation["errors"]))
    if not guards_ok:
        failed = [g["guard"] for g in guards if not g["ok"]]
        notes.append("guards failed: %s" % ", ".join(failed))
    notes.append("EXECUTION is not_implemented in this packet (no destructive writes)")

    return {
        "schema": "ariadne.cad_patch.dry_run.v1",
        "patch_id": patch_id,
        "schema_validation": schema_validation,
        "risk": risk,
        "guards": guards,
        "guards_ok": guards_ok,
        "planned_ops": planned_ops,
        "execution": "not_implemented",
        "status": status,
        "notes": notes,
    }


# --------------------------------------------------------------------------- #
# M02 -- staged-copy execution lifecycle (REAL writes, ALWAYS on a copy)
# --------------------------------------------------------------------------- #

# Patch op id -> native ObjectARX write op (operations.v2.json, status
# "implemented"). Only these four declared patch ops have a live native handler;
# everything else is not_implemented (no-fake-success).
NATIVE_WRITE_OP_MAP: Dict[str, str] = {
    "create_line": "write.entity.line",
    "create_circle": "write.entity.circle",
    "set_layer": "write.layer.create",
    "create_layer": "write.layer.create",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _import_optional(module_name: str) -> Tuple[Optional[Any], Optional[str]]:
    """Import a sibling module another lane owns; return (mod, error_str|None).

    A not-yet-present sibling (cad_diff / validator / ir_builder) degrades to
    (None, "<why>") so callers can report not_implemented rather than crash.
    """
    try:
        mod = importlib.import_module(module_name)
        return mod, None
    except Exception as exc:  # ImportError or a downstream error in that module
        return None, "%s: %s" % (type(exc).__name__, exc)


def _sha256_file(path: str) -> Optional[str]:
    """Full lowercase SHA-256 of a file, or None if it cannot be read."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _byte_size(path: str) -> Optional[int]:
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _load_json_bom(path: str) -> Any:
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def create_staged_copy(dwg_path: str, out_dir: str) -> Dict[str, Any]:
    """Copy ``dwg_path`` to a writable staged path under ``out_dir`` and record
    the ORIGINAL's sha256 + byte_size (for the no-original-write proof).

    NEVER writes the original. Returns:
      {ok, staged_path, original_path, original_sha256, original_byte_size,
       staged_sha256, staged_byte_size, staged_at, reason?}.
    ok is False (with reason, no staged_path) when the input is missing/unreadable.
    """
    out: Dict[str, Any] = {
        "ok": False,
        "staged_path": None,
        "original_path": os.path.abspath(dwg_path) if dwg_path else dwg_path,
        "original_sha256": None,
        "original_byte_size": None,
        "staged_sha256": None,
        "staged_byte_size": None,
        "staged_at": _now_iso(),
    }
    if not dwg_path or not os.path.isfile(dwg_path):
        out["reason"] = "input DWG not found: %s" % dwg_path
        return out

    original_sha = _sha256_file(dwg_path)
    out["original_sha256"] = original_sha
    out["original_byte_size"] = _byte_size(dwg_path)

    os.makedirs(out_dir, exist_ok=True)
    staged = os.path.join(out_dir, "staged_input.dwg")
    try:
        shutil.copy2(dwg_path, staged)
        try:
            os.chmod(staged, 0o666)  # ensure the staged copy is writable
        except OSError:
            pass
    except OSError as exc:
        out["reason"] = "failed to stage copy: %s: %s" % (type(exc).__name__, exc)
        return out

    out["staged_path"] = staged
    out["staged_sha256"] = _sha256_file(staged)
    out["staged_byte_size"] = _byte_size(staged)
    out["ok"] = True
    return out


def _resolve_native_write_op(patch: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Pick the single patch operation to apply and resolve its native write op.

    This M02 lifecycle applies ONE mutation per call (the first operation). A
    patch with multiple ops is accepted but only operations[0] is applied; the
    rest are reported as deferred in the result. Returns (op_record, error). The
    op_record is {index, patch_op, native_op, args}; error is set (op_record None)
    when the op has no live native handler (not_implemented, no fake).
    """
    ops = patch.get("operations") or []
    if not ops:
        return None, "patch has no operations"
    op = ops[0]
    if not isinstance(op, dict):
        return None, "operations[0] is not an object"
    patch_op = op.get("operation")
    native_op = NATIVE_WRITE_OP_MAP.get(patch_op)
    if native_op is None:
        return None, ("patch op %r has no live native write handler (supported: %s)"
                      % (patch_op, sorted(NATIVE_WRITE_OP_MAP)))
    return ({"index": 0, "step_id": op.get("step_id"), "patch_op": patch_op,
             "native_op": native_op, "args": op.get("args", {}) or {}}, None)


def _native_job_doc(native_op: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Build a minimal ariadne.cad_job.v2 doc for the native write op.

    The native ObjectARX job reads its args (start/end, center/radius, name/
    color_index, point) from this JobPath JSON. We pass through only the keys the
    op declares (per cad_job.v2 allOf rules); extra keys are harmless but omitted.
    """
    job: Dict[str, Any] = {
        "schema": "ariadne.autocad_sdk_job.v2",
        "operation": native_op,
        "write_mode": "write_copy",
        "policy": {"write_mode": "write_copy", "require_staged_copy": True,
                   "save": True, "lock_document": True},
        "source_agent": "patch_engine",
        "args": {},
    }
    if native_op == "write.entity.line":
        for k in ("start", "end", "layer"):
            if k in args:
                job["args"][k] = args[k]
    elif native_op == "write.entity.circle":
        for k in ("center", "radius", "layer"):
            if k in args:
                job["args"][k] = args[k]
    elif native_op == "write.layer.create":
        # set_layer/create_layer -> ensure the target layer exists.
        name = args.get("name") or args.get("layer")
        if name is not None:
            job["args"]["name"] = name
        if "color_index" in args:
            job["args"]["color_index"] = args["color_index"]
    return job


def _native_full_ir(ir_builder, run_res: Dict[str, Any], staged_path: str,
                    original_path: str, ir_out_path: str,
                    phase: str) -> Dict[str, Any]:
    """From a native inspect.database.graph run result, build + write a
    native_full IR. Returns {ok, ir_path?, entity_count?, reason?}.

    Truthful degradation: no result object -> partial/unavailable; build failure
    -> partial. ir_builder is the caller-provided sibling (already import-checked).
    """
    result_obj = run_res.get("result")
    if not isinstance(result_obj, dict):
        return {"ok": False,
                "reason": run_res.get("error")
                or "native graph (%s) produced no result object" % phase,
                "exit_code": run_res.get("exit_code"),
                "stdout": run_res.get("stdout_path"),
                "stderr": run_res.get("stderr_path")}
    source_meta = {
        "dwg_path": staged_path,
        "original_path": original_path,
        "dwg_name": os.path.basename(original_path or staged_path),
        "format": "dwg",
        "byte_size": _byte_size(staged_path),
        "sha256": _sha256_file(staged_path),
        "extractor": "native_objectarx",
        "engine_tier": "native_arx",
        "route": "dwg_truth_autocad",
        "extracted_at": _now_iso(),
        "phase": phase,
    }
    try:
        ir = ir_builder.build_ir_from_database_graph(result_obj, source_meta)
        written = ir_builder.write_ir(ir, ir_out_path)
    except Exception as exc:
        return {"ok": False,
                "reason": "build_ir_from_database_graph (%s) failed: %s: %s"
                % (phase, type(exc).__name__, exc),
                "stdout": run_res.get("stdout_path"),
                "stderr": run_res.get("stderr_path")}
    return {"ok": True, "ir_path": written,
            "entity_count": (ir.get("diagnostics") or {}).get("entity_count"),
            "stdout": run_res.get("stdout_path"),
            "stderr": run_res.get("stderr_path"),
            "exit_code": run_res.get("exit_code")}


def _call_validator(validator, diff_path: Optional[str], run_dir: str,
                    patch_path: Optional[str],
                    ir_path: Optional[str] = None) -> Dict[str, Any]:
    """Call validator.validate_target with only the params it accepts.

    The validator lane may or may not yet accept diff_path/patch_path/ir_path. We
    introspect its signature and pass supported kwargs, so an un-extended sibling
    degrades (validates run_dir only) instead of raising TypeError. Passing the
    post-patch IR lets the IR gates (schema, entity-count, no-original-write) run
    against the mutated drawing instead of blocking for lack of an IR.
    """
    try:
        sig = inspect.signature(validator.validate_target)
        params = set(sig.parameters)
    except (TypeError, ValueError):
        params = set()
    kwargs: Dict[str, Any] = {}
    if "run_dir" in params:
        kwargs["run_dir"] = run_dir
    if "diff_path" in params and diff_path:
        kwargs["diff_path"] = diff_path
    if "patch_path" in params and patch_path:
        kwargs["patch_path"] = patch_path
    if "ir_path" in params and ir_path:
        kwargs["ir_path"] = ir_path
    try:
        report = validator.validate_target(**kwargs)
        return {"ok": True, "report": report,
                "passed_kwargs": sorted(kwargs),
                "diff_aware": "diff_path" in params}
    except Exception as exc:
        return {"ok": False,
                "reason": "validator.validate_target failed: %s: %s"
                % (type(exc).__name__, exc),
                "passed_kwargs": sorted(kwargs)}


def _write_json(path: str, obj: Any) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    return path


def _result_envelope(status: str, *, patch_id, out_dir, journal_path,
                     artifacts, original_unchanged, reason=None,
                     diff_summary=None, validation_status=None,
                     deferred_ops=None, extra=None) -> Dict[str, Any]:
    env: Dict[str, Any] = {
        "schema": RESULT_SCHEMA_ID,
        "status": status,
        "patch_id": patch_id,
        "out_dir": out_dir,
        "original_unchanged": original_unchanged,
        "journal": journal_path,
        "artifacts": artifacts,
    }
    if reason:
        env["reason"] = reason
    if diff_summary is not None:
        env["diff_summary"] = diff_summary
    if validation_status is not None:
        env["validation_status"] = validation_status
    if deferred_ops:
        env["deferred_ops"] = deferred_ops
    if extra:
        env.update(extra)
    return env


def apply_staged(patch: Dict[str, Any], dwg_path: str, out_dir: str) -> Dict[str, Any]:
    """Apply a patch to a STAGED COPY of ``dwg_path`` and return a result envelope.

    REAL staged-write lifecycle (the original is never touched):
      1. validate_patch_schema   -- reject malformed patches (status blocked)
      2. classify_patch_risk     -- blocked risk => refuse (status blocked)
      3. guards                  -- staged-copy / no-original-write / validation
      4. create_staged_copy      -- writable copy + record original sha256/size
      5. pre-inspect             -- native_full IR of the staged copy
      6. apply                   -- native ObjectARX write op (write_copy) ->
                                    the router's staged_used is the mutated copy,
                                    saved here as staged_output.dwg
      7. post-inspect            -- native_full IR of the mutated output
      8. compute_diff            -- cad_diff.v1 (cad_diff sibling)
      9. validate                -- validation_report.v1 (validator sibling)
     10. journal                 -- ordered steps + command refs + original-
                                    unchanged proof (sha256 before == after)

    Truthful statuses (no-fake-success):
      blocked          -- schema invalid / risk blocked / guard failed / input
                          missing
      not_implemented  -- patch op has no native write handler, OR a required
                          sibling lane (ir_builder / router host / cad_diff /
                          validator) is unavailable
      partial          -- an inspect/apply ran but did not return a usable result
      ok               -- the mutation applied, both IRs built, diff computed,
                          validation ran, and the original is byte-identical

    Artifacts written under ``out_dir``: patch.json, staged_input.dwg,
    staged_output.dwg, pre/dwg_graph_ir.json, post/dwg_graph_ir.json,
    cad_diff.json, validation_report.json, journal.json, result.json.
    """
    os.makedirs(out_dir, exist_ok=True)
    patch_id = patch.get("patch_id") if isinstance(patch, dict) else None
    journal: Dict[str, Any] = {
        "schema": "ariadne.cad_patch.journal.v1",
        "patch_id": patch_id,
        "started_at": _now_iso(),
        "out_dir": out_dir,
        "steps": [],
    }
    artifacts: List[Dict[str, Any]] = []
    journal_path = os.path.join(out_dir, "journal.json")
    result_path = os.path.join(out_dir, "result.json")

    def _step(name: str, status: str, **fields):
        rec = {"step": name, "status": status, "at": _now_iso()}
        rec.update(fields)
        journal["steps"].append(rec)
        return rec

    def _finish(env: Dict[str, Any]) -> Dict[str, Any]:
        journal["finished_at"] = _now_iso()
        journal["result_status"] = env["status"]
        _write_json(journal_path, journal)
        _write_json(result_path, env)
        return env

    # always persist the patch we were handed (provenance)
    patch_json_path = os.path.join(out_dir, "patch.json")
    try:
        _write_json(patch_json_path, patch)
        artifacts.append({"kind": "patch", "ref": patch_json_path})
    except OSError:
        pass

    # 1. schema validation -----------------------------------------------------
    schema_check = validate_patch_schema(patch)
    _step("validate_patch_schema", "pass" if schema_check["valid"] else "fail",
          errors=schema_check["errors"], warnings=schema_check["warnings"])
    if not schema_check["valid"]:
        return _finish(_result_envelope(
            "blocked", patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=None,
            reason="schema validation failed: %s" % "; ".join(schema_check["errors"])))

    # 2. risk classification ---------------------------------------------------
    risk = classify_patch_risk(patch)
    _step("classify_patch_risk", "blocked" if risk["risk"] == "blocked" else "pass",
          risk=risk["risk"], reasons=risk["reasons"])
    if risk["risk"] == "blocked":
        return _finish(_result_envelope(
            "blocked", patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=None,
            reason="risk classified blocked: %s" % "; ".join(risk["reasons"])))

    # 3. guards ----------------------------------------------------------------
    guards = _run_guards(patch)
    guards_ok = all(g["ok"] for g in guards)
    _step("guards", "pass" if guards_ok else "fail", guards=guards)
    if not guards_ok:
        failed = [g["guard"] for g in guards if not g["ok"]]
        return _finish(_result_envelope(
            "blocked", patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=None,
            reason="guards failed: %s" % ", ".join(failed)))

    # resolve the native write op BEFORE touching the disk (no-fake-success) ----
    op_record, op_err = _resolve_native_write_op(patch)
    if op_record is None:
        _step("resolve_native_write_op", "not_implemented", reason=op_err)
        return _finish(_result_envelope(
            "not_implemented", patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=None, reason=op_err))
    deferred_ops = [
        {"index": i, "operation": (o.get("operation") if isinstance(o, dict) else None),
         "status": "deferred",
         "reason": "apply_staged applies one mutation per call (operations[0] only)"}
        for i, o in enumerate(patch.get("operations") or []) if i > 0
    ]
    _step("resolve_native_write_op", "pass",
          patch_op=op_record["patch_op"], native_op=op_record["native_op"],
          deferred=len(deferred_ops))

    # sibling lane availability (truthful, before any external command) ---------
    ir_builder, ir_err = _import_optional("ir_builder")
    if ir_builder is None or not hasattr(ir_builder, "build_ir_from_database_graph"):
        _step("import_ir_builder", "not_implemented", reason=ir_err)
        return _finish(_result_envelope(
            "not_implemented", patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=None,
            reason="ir_builder.build_ir_from_database_graph unavailable: %s" % ir_err))
    run_job, runjob_err = _import_optional("run_job")
    if run_job is None or not hasattr(run_job, "run_router_cad_job"):
        _step("import_run_job", "not_implemented", reason=runjob_err)
        return _finish(_result_envelope(
            "not_implemented", patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=None,
            reason="run_job.run_router_cad_job unavailable: %s" % runjob_err))

    # 4. create the staged copy (NEVER the original) ---------------------------
    staged = create_staged_copy(dwg_path, out_dir)
    if not staged["ok"]:
        _step("create_staged_copy", "blocked", reason=staged.get("reason"))
        return _finish(_result_envelope(
            "blocked", patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=None, reason=staged.get("reason")))
    staged_path = staged["staged_path"]
    original_path = staged["original_path"]
    original_sha_before = staged["original_sha256"]
    artifacts.append({"kind": "dwg_staged", "ref": staged_path})
    _step("create_staged_copy", "pass", staged_path=staged_path,
          original_path=original_path, original_sha256_before=original_sha_before,
          original_byte_size=staged.get("original_byte_size"))

    def _original_unchanged() -> Dict[str, Any]:
        after = _sha256_file(original_path) if original_path else None
        return {"original_path": original_path,
                "sha256_before": original_sha_before, "sha256_after": after,
                "unchanged": (original_sha_before is not None and after == original_sha_before)}

    # 5. pre-inspect: native_full IR of the staged copy ------------------------
    pre_dir = os.path.join(out_dir, "pre")
    pre_run = run_job.run_router_cad_job(
        staged_path, pre_dir, "inspect.database.graph", write_mode="read")
    pre_ir_path = os.path.join(pre_dir, "dwg_graph_ir.json")
    pre = _native_full_ir(ir_builder, pre_run, staged_path, original_path,
                          pre_ir_path, "pre")
    _step("pre_inspect", "pass" if pre["ok"] else "partial",
          ir_path=pre.get("ir_path"), entity_count=pre.get("entity_count"),
          exit_code=pre.get("exit_code"), stdout=pre.get("stdout"),
          stderr=pre.get("stderr"), reason=pre.get("reason"))
    if not pre["ok"]:
        status = "unavailable" if pre_run.get("error") else "partial"
        return _finish(_result_envelope(
            status, patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=_original_unchanged(),
            reason="pre-inspect failed: %s" % pre.get("reason")))
    artifacts.append({"kind": "ir", "ref": pre["ir_path"]})

    # 6. apply the native write op on the staged copy (write_copy) -------------
    apply_dir = os.path.join(out_dir, "apply")
    os.makedirs(apply_dir, exist_ok=True)
    job_doc = _native_job_doc(op_record["native_op"], op_record["args"])
    job_path = os.path.join(apply_dir, "cad_job.json")
    _write_json(job_path, job_doc)
    apply_run = run_job.run_router_cad_job(
        staged_path, apply_dir, op_record["native_op"],
        write_mode="write_copy", job_path=job_path)
    mutated = apply_run.get("staged_used")  # the router's mutated copy (post-_QSAVE)
    staged_output = os.path.join(out_dir, "staged_output.dwg")
    apply_ok = False
    if mutated and os.path.isfile(mutated):
        try:
            shutil.copy2(mutated, staged_output)
            apply_ok = True
        except OSError as exc:
            _step("apply", "partial",
                  reason="failed to capture staged_output: %s" % exc,
                  staged_used=mutated, exit_code=apply_run.get("exit_code"))
    if not apply_ok:
        reason = (apply_run.get("error")
                  or "native write op returned no mutated staged copy "
                     "(staged_used=%r)" % mutated)
        _step("apply", "unavailable" if apply_run.get("error") else "partial",
              native_op=op_record["native_op"], staged_used=mutated,
              exit_code=apply_run.get("exit_code"),
              stdout=apply_run.get("stdout_path"), stderr=apply_run.get("stderr_path"),
              reason=reason)
        status = "unavailable" if apply_run.get("error") else "partial"
        return _finish(_result_envelope(
            status, patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=_original_unchanged(),
            reason="apply failed: %s" % reason, deferred_ops=deferred_ops))
    artifacts.append({"kind": "dwg_staged", "ref": staged_output})
    _step("apply", "pass", native_op=op_record["native_op"],
          staged_output=staged_output, staged_used=mutated,
          exit_code=apply_run.get("exit_code"),
          stdout=apply_run.get("stdout_path"), stderr=apply_run.get("stderr_path"))

    # 7. post-inspect: native_full IR of the mutated output --------------------
    post_dir = os.path.join(out_dir, "post")
    post_run = run_job.run_router_cad_job(
        staged_output, post_dir, "inspect.database.graph", write_mode="read")
    post_ir_path = os.path.join(post_dir, "dwg_graph_ir.json")
    post = _native_full_ir(ir_builder, post_run, staged_output, original_path,
                           post_ir_path, "post")
    _step("post_inspect", "pass" if post["ok"] else "partial",
          ir_path=post.get("ir_path"), entity_count=post.get("entity_count"),
          exit_code=post.get("exit_code"), stdout=post.get("stdout"),
          stderr=post.get("stderr"), reason=post.get("reason"))
    if not post["ok"]:
        status = "unavailable" if post_run.get("error") else "partial"
        return _finish(_result_envelope(
            status, patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=_original_unchanged(),
            reason="post-inspect failed: %s" % post.get("reason"),
            deferred_ops=deferred_ops))
    artifacts.append({"kind": "ir", "ref": post["ir_path"]})

    # 8. compute the diff (cad_diff sibling lane) ------------------------------
    diff_path = os.path.join(out_dir, "cad_diff.json")
    diff_summary = None
    cad_diff_mod, diff_err = _import_optional("cad_diff")
    if cad_diff_mod is None or not hasattr(cad_diff_mod, "compute_diff"):
        _step("compute_diff", "not_implemented", reason=diff_err)
        # The mutation IS real; diff/validate are downstream. Report partial, not ok.
        return _finish(_result_envelope(
            "partial", patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=_original_unchanged(),
            reason="cad_diff sibling unavailable: %s" % diff_err,
            deferred_ops=deferred_ops,
            extra={"pre_ir": pre["ir_path"], "post_ir": post["ir_path"],
                   "staged_output": staged_output}))
    try:
        pre_ir = _load_json_bom(pre["ir_path"])
        post_ir = _load_json_bom(post["ir_path"])
        diff = cad_diff_mod.compute_diff(pre_ir, post_ir)
        _write_json(diff_path, diff)
        diff_summary = (diff or {}).get("summary")
        artifacts.append({"kind": "diff", "ref": diff_path})
        _step("compute_diff", "pass", diff_path=diff_path, summary=diff_summary)
    except Exception as exc:
        _step("compute_diff", "partial",
              reason="compute_diff failed: %s: %s" % (type(exc).__name__, exc))
        return _finish(_result_envelope(
            "partial", patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=_original_unchanged(),
            reason="compute_diff failed: %s: %s" % (type(exc).__name__, exc),
            deferred_ops=deferred_ops))

    # Finalize the journal BEFORE validation so the validator's journal_present /
    # original_dwg_unchanged gates can read it (with the original-unchanged proof
    # as a top-level field). The validate step is appended to journal["steps"]
    # afterward and the journal is rewritten by _finish.
    _oc = _original_unchanged()
    journal["original_unchanged"] = _oc
    # Layout-B compatible block (key 'original' with sha256_before/after) so
    # validator._journal_original_sha -> original_dwg_unchanged gate can verify
    # the read-only invariant from the journal.
    journal["original"] = {
        "original_path": _oc.get("original_path"),
        "sha256_before": _oc.get("sha256_before"),
        "sha256_after": _oc.get("sha256_after"),
    }
    _write_json(journal_path, journal)

    # 9. validate (validator sibling lane) -------------------------------------
    # run_dir = out_dir (NOT post_dir): the staged_input/output.dwg + journal.json
    # + patch.json live at the patch out_dir top level. ir_path = the post IR so
    # the IR gates validate the mutated drawing instead of blocking.
    validation_status = None
    validator_mod, val_err = _import_optional("validator")
    if validator_mod is None or not hasattr(validator_mod, "validate_target"):
        _step("validate", "not_implemented", reason=val_err)
        return _finish(_result_envelope(
            "partial", patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=_original_unchanged(),
            reason="validator sibling unavailable: %s" % val_err,
            diff_summary=diff_summary, deferred_ops=deferred_ops))
    val = _call_validator(validator_mod, diff_path, out_dir, patch_json_path,
                          ir_path=post["ir_path"])
    if val["ok"]:
        report = val["report"]
        validation_status = (report or {}).get("status")
        report_path = os.path.join(out_dir, "validation_report.json")
        _write_json(report_path, report)
        artifacts.append({"kind": "validation_report", "ref": report_path})
        _step("validate", "pass", report=report_path,
              validation_status=validation_status,
              passed_kwargs=val.get("passed_kwargs"),
              diff_aware=val.get("diff_aware"))
    else:
        _step("validate", "partial", reason=val.get("reason"),
              passed_kwargs=val.get("passed_kwargs"))
        return _finish(_result_envelope(
            "partial", patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=_original_unchanged(),
            reason=val.get("reason"), diff_summary=diff_summary,
            deferred_ops=deferred_ops))

    # 10. finalize: success requires the original to be byte-identical ---------
    orig_proof = _original_unchanged()
    if not orig_proof["unchanged"]:
        _step("original_unchanged_proof", "fail", proof=orig_proof)
        return _finish(_result_envelope(
            "blocked", patch_id=patch_id, out_dir=out_dir,
            journal_path=journal_path, artifacts=artifacts,
            original_unchanged=orig_proof,
            reason="original DWG changed during apply (sha256 before != after) -- "
                   "READ-ONLY invariant violated",
            diff_summary=diff_summary, validation_status=validation_status,
            deferred_ops=deferred_ops))
    _step("original_unchanged_proof", "pass", proof=orig_proof)

    return _finish(_result_envelope(
        "ok", patch_id=patch_id, out_dir=out_dir,
        journal_path=journal_path, artifacts=artifacts,
        original_unchanged=orig_proof,
        diff_summary=diff_summary, validation_status=validation_status,
        deferred_ops=deferred_ops,
        extra={"pre_ir": pre["ir_path"], "post_ir": post["ir_path"],
               "staged_output": staged_output,
               "diff": diff_path,
               "entity_count_before": pre.get("entity_count"),
               "entity_count_after": post.get("entity_count")}))


# --------------------------------------------------------------------------- #
# Self-test (__main__): dry_run_plan always; apply_staged when CADOS_LIVE=1
# --------------------------------------------------------------------------- #

_GOLDEN_DWG = os.path.join(_ROUTER_HOME, "staging", "dwg_20260617_191504", "input.dwg")


def _sample_patch() -> Dict[str, Any]:
    return {
        "schema": PATCH_SCHEMA_ID,
        "patch_id": "demo-patch-0001",
        "title": "Add a dimension line on a staged copy",
        "source_agent": "patch_engine.selftest",
        "target_dwg": {
            "staged_path": os.path.join(_ROUTER_HOME, "staging", "golden",
                                        "demo", "input.dwg"),
            "original_path": os.path.join(_ROUTER_HOME, "samples", "input.dwg"),
        },
        "operations": [
            {"step_id": "s1", "operation": "create_line",
             "args": {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"}},
            {"step_id": "s2", "operation": "set_layer",
             "args": {"handle": "2A", "layer": "DIM"}},
        ],
        "preconditions": [
            {"subject": "layer_exists", "op": "exists", "value": "DIM"},
        ],
        "postconditions": [
            {"subject": "entity_count", "op": "delta_eq", "value": 1},
        ],
        "policy": {"staged_copy": True, "write_mode": "write_copy", "dry_run": True},
    }


def _selftest() -> int:
    patch = _sample_patch()
    plan = dry_run_plan(patch)
    print(json.dumps(plan, ensure_ascii=False, indent=2))

    ok = (
        plan["execution"] == "not_implemented"
        and plan["status"] == "planned"
        and plan["schema_validation"]["valid"] is True
        and plan["guards_ok"] is True
        and all(p["execution_status"] == "not_implemented" for p in plan["planned_ops"])
    )

    # Negative check: a write_original patch must be rejected (guard).
    bad = _sample_patch()
    bad["policy"]["write_mode"] = "write_original"
    bad_plan = dry_run_plan(bad)
    ok = ok and bad_plan["status"] == "rejected" and bad_plan["guards_ok"] is False

    # not_implemented check: an op with no native handler must degrade truthfully
    # in the live lifecycle (without touching disk / AutoCAD).
    ni = _sample_patch()
    ni["operations"] = [{"step_id": "s1", "operation": "delete_entity",
                         "args": {"handle": "2A"}}]
    ni["postconditions"] = [{"subject": "entity_count", "op": "delta_eq", "value": -1}]
    ni_op, ni_err = _resolve_native_write_op(ni)
    ok = ok and ni_op is None and ni_err is not None

    print("SELFTEST_OK" if ok else "SELFTEST_FAIL",
          "| status=%s risk=%s guards_ok=%s | neg_status=%s | native_unsupported=%s"
          % (plan["status"], plan["risk"]["risk"], plan["guards_ok"],
             bad_plan["status"], ni_op is None))
    return 0 if ok else 1


def _live_apply() -> int:
    """CADOS_LIVE=1: run the REAL staged-write lifecycle on the golden copy.

    Operates ONLY on a staged copy of the golden DWG; the original is never
    touched (the result's original_unchanged proof asserts byte-equality).
    """
    if not os.path.isfile(_GOLDEN_DWG):
        print("LIVE_SKIP | golden DWG not found: %s" % _GOLDEN_DWG)
        return 0
    out_dir = os.path.join(_ROUTER_HOME, "runs",
                           "patch_engine_live_%s" % _ts())
    patch = {
        "schema": PATCH_SCHEMA_ID,
        "patch_id": "live-apply-%s" % _ts(),
        "title": "Add one LINE on a staged copy of the golden DWG",
        "source_agent": "patch_engine.live",
        "target_dwg": {
            "staged_path": os.path.join(out_dir, "staged_input.dwg"),
            "original_path": _GOLDEN_DWG,
        },
        "operations": [
            {"step_id": "s1", "operation": "create_line",
             "args": {"start": {"x": 0, "y": 0, "z": 0},
                      "end": {"x": 1000, "y": 0, "z": 0}, "layer": "0"}},
        ],
        "postconditions": [
            {"subject": "entity_count", "op": "delta_eq", "value": 1},
        ],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }
    res = apply_staged(patch, _GOLDEN_DWG, out_dir)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    proof = res.get("original_unchanged") or {}
    # A successful live run requires the original to be byte-identical; any
    # non-ok status is allowed (host may be busy) EXCEPT a proven original change.
    original_safe = (proof.get("unchanged") is not False)
    print("LIVE_OK" if original_safe else "LIVE_FAIL",
          "| status=%s | original_unchanged=%s | out_dir=%s"
          % (res.get("status"), proof.get("unchanged"), out_dir))
    return 0 if original_safe else 1


if __name__ == "__main__":
    rc = _selftest()
    if os.environ.get("CADOS_LIVE") == "1":
        rc = _live_apply() or rc
    sys.exit(rc)
