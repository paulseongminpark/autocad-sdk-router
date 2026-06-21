#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_engine.py -- Lane E SAFE patch shell for the CAD OS Layer.

A patch is an ``ariadne.cad_patch.v1`` document (conforms
``schemas/cad_patch.v1.schema.json``): an ordered, idempotent batch of CAD
mutations that ALWAYS target a STAGED copy of a drawing, never an original in
place.

This module is a SAFE SHELL. In this packet it performs NO destructive writes:
  * validate_patch_schema(patch)  -- structural validation against cad_patch.v1
  * classify_patch_risk(patch)    -- low/medium/high/blocked risk classification
  * dry_run_plan(patch)           -- resolves each op to its registry mapping and
                                     returns a PLAN; it does not execute anything
  * guards: reject_write_original_by_default, require_staged_copy,
            require_validation

EXECUTION of the declared mutation ops
(create_line / create_polyline / create_text / set_layer / move_entity /
delete_entity) is intentionally ``not_implemented`` here -- the plan records the
registry op each would dispatch to, but the runner is out of scope for this
packet (no destructive writes).

Hard rules: standard library ONLY; no-fake-success (unimplemented => explicit
``not_implemented``); never plan a write to an original; a patch with
``policy.staged_copy != true`` is rejected.

Public API:
    PATCH_SCHEMA_ID, DECLARED_OPS, OP_REGISTRY_MAP
    validate_patch_schema(patch) -> dict
    classify_patch_risk(patch)   -> dict
    dry_run_plan(patch)          -> dict
    reject_write_original_by_default(patch) -> dict
    require_staged_copy(patch)   -> dict
    require_validation(patch)    -> dict
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)
_OPERATIONS_V2 = os.path.join(_ROUTER_HOME, "config", "operations.v2.json")
_JSON_ENCODING = "utf-8-sig"

PATCH_SCHEMA_ID = "ariadne.cad_patch.v1"

# The declared high-level mutation operations this shell understands, mapped to
# the operation-registry id (config/operations.v2.json) that would carry them.
# The patch-apply pipeline itself routes through 'apply.patch' (a stub op today),
# so EXECUTION of any of these is not_implemented in this packet.
OP_REGISTRY_MAP: Dict[str, str] = {
    "create_line": "write.entity.create",
    "create_polyline": "write.entity.create",
    "create_text": "write.entity.create",
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
# Self-test (__main__): demo a dry_run_plan on a sample patch
# --------------------------------------------------------------------------- #

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

    print("SELFTEST_OK" if ok else "SELFTEST_FAIL",
          "| status=%s risk=%s guards_ok=%s | neg_status=%s"
          % (plan["status"], plan["risk"]["risk"], plan["guards_ok"],
             bad_plan["status"]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest())
