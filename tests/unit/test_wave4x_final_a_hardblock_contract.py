#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Final A hardblock reimplementation contract tests.

Every remaining blocked operation must be a deliberate, evidenced safety block:
not agent-exposed, backed by an allowed blocker code, audited against safe
replacement routes, and pinned by a test reference.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "operations.v2.json"

PACKET_ID = "WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION"
THIS_TEST = "tests/unit/test_wave4x_final_a_hardblock_contract.py"

ALLOWED_CODES = {
    "SDK_NOT_EXPOSED",
    "HOST_UNAVAILABLE",
    "LICENSE_UNAVAILABLE",
    "SAFETY_FORBIDDEN",
    "OBJECT_ENABLER_REQUIRED",
    "ORIGINAL_WRITE_FORBIDDEN",
}

AUDIT_FIELDS = {
    "why_no_typed_safe_implementation",
    "why_no_read_status_introspection_subset",
    "why_no_staged_copy_implementation",
    "why_no_attended_dedicated_instance_implementation",
    "why_no_policy_gated_replacement_route",
    "non_agent_exposure_test",
}

RAW_COMMAND_BLOCKS = {
    "automate.com.send_command",
    "command.invoke.coroutine",
    "command.invoke.sync",
    "command.invoke.sync.resbuf",
    "command.menu.invoke",
    "command.queue.post",
    "doc.sendstring",
}

ASSOC_BLOCKS = {
    "define.assocarray.create",
    "define.assocarray.path",
    "define.assocarray.polar",
    "define.assocarray.rectangular",
    "define.assocsurface.blend",
    "define.assocsurface.extrude",
    "define.assocsurface.fillet",
    "define.assocsurface.loft",
    "define.assocsurface.offset",
    "define.assocsurface.patch",
    "define.assocsurface.result",
    "define.assocsurface.trim",
    "edit.assocarray.explode",
    "edit.assocarray.item",
    "edit.assocarray.itemReplace",
    "edit.assocarray.reset",
    "edit.assocarray.source",
    "edit.assocarray.transform",
    "inspect.assocaction.evaluate",
    "inspect.assocnetwork.evaluate",
}


def _ops_by_id() -> dict[str, dict]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    return {op["id"]: op for op in data["operations"]}


def _blocked(ops: dict[str, dict]) -> dict[str, dict]:
    return {oid: op for oid, op in ops.items() if op.get("status") == "blocked"}


def _blocker_code(op: dict) -> str:
    return (op.get("blocked_reason") or "").split(":", 1)[0]


def test_every_remaining_hardblock_has_final_a_audit_and_non_exposure():
    blocked = _blocked(_ops_by_id())
    assert len(blocked) == 29

    for oid, op in blocked.items():
        code = _blocker_code(op)
        assert code in ALLOWED_CODES, oid
        assert op.get("agent_exposed") is False, oid
        assert (op.get("policy") or {}).get("agent_exposed") is False, oid
        assert op.get("blocker_ref"), oid
        assert op.get("evidence_refs"), oid

        audit = op.get("hardblock_audit") or {}
        assert audit.get("packet") == PACKET_ID, oid
        assert audit.get("allowed_hardblock_reason") == code, oid
        assert set(audit) >= AUDIT_FIELDS, oid
        for field in AUDIT_FIELDS:
            assert audit.get(field), f"{oid} missing {field}"
        assert audit["non_agent_exposure_test"] in (op.get("tests") or []), oid


def test_raw_command_blocks_have_typed_replacement_policy_not_agent_surface():
    ops = _ops_by_id()
    for oid in RAW_COMMAND_BLOCKS:
        op = ops[oid]
        assert op["status"] == "blocked", oid
        assert _blocker_code(op) == "SAFETY_FORBIDDEN", oid
        assert op["handler"]["router_lane"] is None, oid
        assert op["handler"]["dispatcher_symbol"] is None, oid
        assert op.get("replacement_ref"), oid
        audit = op["hardblock_audit"]
        assert "typed" in audit["why_no_policy_gated_replacement_route"].lower(), oid
        assert "raw command" in audit["why_no_typed_safe_implementation"].lower(), oid


def test_assoc_solver_blocks_point_to_existing_safe_introspection_routes():
    ops = _ops_by_id()
    implemented_replacements = {
        "inspect.assocarray.identify",
        "inspect.assocmanager.state",
        "inspect.assocnetwork.get",
        "inspect.assocnetwork.iterate",
        "inspect.assocaction.dependencies",
        "inspect.assocaction.requestToEvaluate",
        "inspect.assocsurface.topology",
        "repair.assocdata.audit",
    }
    for repl in implemented_replacements:
        assert ops[repl]["status"] == "implemented", repl

    for oid in ASSOC_BLOCKS:
        op = ops[oid]
        assert op["status"] == "blocked", oid
        assert _blocker_code(op) == "SAFETY_FORBIDDEN", oid
        assert op.get("replacement_ref"), oid
        refs = set(part.strip() for part in op["replacement_ref"].split("+"))
        assert refs & implemented_replacements, oid


def test_ole_and_lifecycle_blocks_are_host_scoped_and_replaced_by_metadata_status_routes():
    ops = _ops_by_id()
    for repl in ("automate.com.wrapper_for_object", "module.lifecycle.unload", "module.lifecycle.on_unload_dwg"):
        assert ops[repl]["status"] == "implemented", repl

    for oid in ("embed.ole.frame", "module.lifecycle.on_ole_unload"):
        op = ops[oid]
        assert op["status"] == "blocked", oid
        assert _blocker_code(op) == "HOST_UNAVAILABLE", oid
        assert op.get("agent_exposed") is False, oid
        assert op.get("replacement_ref"), oid
        assert THIS_TEST in (op.get("tests") or []), oid
