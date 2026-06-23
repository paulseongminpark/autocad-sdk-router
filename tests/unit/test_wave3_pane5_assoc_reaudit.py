#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wave3 Pane5 associativity re-audit registry checks."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "operations.v2.json"

CALLBACK_INTROSPECTION = {
    "config.assoceval.callback",
    "config.constraint.globalCallback",
}

IMPLEMENTED_STAGED_ASSOC = {
    "edit.assocdata.xref",
    "repair.assocdata.audit",
}

BLOCKED_ASSOC_SOLVER_OR_MODELER = {
    "define.assocsurface.blend",
    "define.assocsurface.extrude",
    "define.assocsurface.fillet",
    "define.assocsurface.loft",
    "define.assocsurface.offset",
    "define.assocsurface.patch",
    "define.assocsurface.result",
    "define.assocsurface.trim",
    "inspect.assocaction.evaluate",
    "inspect.assocnetwork.evaluate",
    "define.assocarray.create",
    "define.assocarray.rectangular",
    "define.assocarray.polar",
    "define.assocarray.path",
    "edit.assocarray.item",
    "edit.assocarray.itemReplace",
    "edit.assocarray.reset",
    "edit.assocarray.source",
    "edit.assocarray.transform",
    "edit.assocarray.explode",
    "inspect.assocsurface.topology",
}


def _ops_by_id() -> dict[str, dict]:
    return {
        op["id"]: op
        for op in json.loads(REGISTRY.read_text(encoding="utf-8-sig"))["operations"]
    }


def test_callback_ops_reaudited_to_safe_introspection_implemented():
    ops = _ops_by_id()
    for oid in CALLBACK_INTROSPECTION:
        op = ops[oid]
        assert op["status"] == "implemented"
        assert op["handler"]["dispatcher_symbol"] == "m08kcDispatch"
        assert op["handler"]["router_lane"] == "ARIADNE_NATIVE_JOB"
        assert op["policy"]["agent_exposed"] is True
        assert op["policy"]["risk_class"] == "read_safe"
        assert "tests/unit/test_m08kc_handlers.py" in op["tests"]
        joined_evidence = "\n".join(op.get("evidence_refs", []))
        assert "WAVE3_PANE5_ASSOCIATIVITY_REAUDIT" in joined_evidence


def test_reopened_assoc_ops_are_implemented_with_staged_write_evidence():
    ops = _ops_by_id()
    assert len(IMPLEMENTED_STAGED_ASSOC) == 2
    for oid in IMPLEMENTED_STAGED_ASSOC:
        op = ops[oid]
        assert op["status"] == "implemented", oid
        assert op["handler"]["dispatcher_symbol"] == "m08kcDispatch", oid
        assert op["policy"]["no_original_write_default"] is True, oid
        evidence = "\n".join(op.get("evidence_refs", []))
        assert "WAVE4X_DB_TXN_WRITE" in evidence, oid


def test_remaining_pane5_assoc_ops_have_real_blockers_after_reaudit():
    ops = _ops_by_id()
    assert len(BLOCKED_ASSOC_SOLVER_OR_MODELER) == 21
    for oid in BLOCKED_ASSOC_SOLVER_OR_MODELER:
        op = ops[oid]
        assert op["status"] == "blocked", oid
        reason = op.get("blocked_reason") or ""
        assert reason.startswith(("SAFETY_FORBIDDEN", "SDK_NOT_EXPOSED", "OBJECT_ENABLER_REQUIRED")), oid
        assert "catalogued" not in reason.lower()
        evidence = "\n".join(op.get("evidence_refs", []))
        assert "WAVE3_PANE5_ASSOCIATIVITY_REAUDIT" in evidence, oid
