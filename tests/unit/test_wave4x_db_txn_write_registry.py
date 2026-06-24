#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WAVE4X Pane 5 registry closeout checks.

Pins the staged-write reopen/deprecation decisions landed by the DB transaction /
object-lifecycle wave so they cannot silently drift back to blocked or catalog-only
policy without failing CI first.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "operations.v2.json"
HOST_MATRIX = ROOT / "config" / "host_matrix.v2.json"

REOPENED = {
    "edit.assocdata.xref",
    "repair.assocdata.audit",
}

STAGED_SAFE_RESIDUAL = {
    "transaction.manager.start",
    "transaction.manager.get_object",
    "write.object.close",
    "write.object.upgrade_open",
    "write.object.downgrade_open",
    "write.object.create_ext_dict",
    "write.regapp.register",
    "write.dictionary.set",
    "write.entity.set_xdata",
    "write.block.append_entity",
    "transform.database.deep_clone",
    "transform.database.insert_block",
}


def _ops_by_id() -> dict[str, dict]:
    return {
        op["id"]: op
        for op in json.loads(REGISTRY.read_text(encoding="utf-8-sig"))["operations"]
    }


def test_reopened_assoc_ops_are_implemented_with_staged_write_policy():
    ops = _ops_by_id()
    for oid in REOPENED:
        op = ops[oid]
        assert op["status"] == "implemented", oid
        assert op["handler"]["dispatcher_symbol"] == "m08kcDispatch", oid
        assert op["handler"]["router_lane"] == "ARIADNE_NATIVE_JOB", oid
        assert op["write_level"]["default_write_mode"] == "write_copy", oid
        assert op["write_level"]["allowed_write_modes"] == ["write_copy"], oid
        assert op["policy"]["status_policy"] == "implemented", oid
        assert op["policy"]["no_original_write_default"] is True, oid
        evidence = "\n".join(op.get("evidence_refs", []))
        assert "WAVE4X_DB_TXN_WRITE" in evidence, oid
        assert "apply_native_staged" in evidence, oid


def test_live_apply_patch_is_deprecated_in_favor_of_staged_governor():
    ops = _ops_by_id()
    op = ops["live.apply_patch"]
    assert op["status"] == "deprecated"
    assert op["policy"]["status_policy"] == "deprecated"
    notes = op.get("notes", "")
    assert "apply.patch" in notes
    assert "apply_native_staged" in notes
    evidence = "\n".join(op.get("evidence_refs", []))
    assert "WAVE4X_DB_TXN_WRITE" in evidence

    host = json.loads(HOST_MATRIX.read_text(encoding="utf-8-sig"))
    live = host["family_host_matrix"]["live.apply_patch"]
    assert live["status"] == "deprecated"


def test_staged_safe_object_lifecycle_ops_are_policy_promoted():
    ops = _ops_by_id()
    for oid in STAGED_SAFE_RESIDUAL:
        op = ops[oid]
        assert op["status"] == "implemented", oid
        assert op["policy"]["status_policy"] == "implemented", oid
        assert op["policy"]["no_original_write_default"] is True, oid
        assert op["handler"]["router_lane"] == "ARIADNE_NATIVE_JOB", oid
        evidence = "\n".join(op.get("evidence_refs", []))
        assert "WAVE4X_DB_TXN_WRITE" in evidence, oid
