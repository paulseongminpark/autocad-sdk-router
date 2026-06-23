#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wave4X Pane3 subentity/BREP registry closure checks."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "operations.v2.json"

CLAIMED = {
    "edit.subentity.add_paths": {
        "dispatcher": "m08gDispatch",
        "write_mode": "write_copy",
    },
    "edit.subentity.delete_paths": {
        "dispatcher": "m08gDispatch",
        "write_mode": "write_copy",
    },
    "edit.subentity.transform": {
        "dispatcher": "m08gDispatch",
        "write_mode": "write_copy",
    },
    "inspect.assocsurface.topology": {
        "dispatcher": "m08kcDispatch",
        "write_mode": "read",
    },
}


def _ops_by_id() -> dict[str, dict]:
    return {
        op["id"]: op
        for op in json.loads(REGISTRY.read_text(encoding="utf-8-sig"))["operations"]
    }


def test_wave4x_claimed_ops_are_implemented():
    ops = _ops_by_id()
    for oid, meta in CLAIMED.items():
        op = ops[oid]
        assert op["status"] == "implemented", oid
        assert op["handler"]["dispatcher_symbol"] == meta["dispatcher"], oid
        assert op["handler"]["router_lane"] == "ARIADNE_NATIVE_JOB", oid
        assert op["write_level"]["default_write_mode"] == meta["write_mode"], oid
        evidence = "\n".join(op.get("evidence_refs") or [])
        assert "WAVE4X_SUBENTITY_BREP" in evidence, oid
        tests = "\n".join(op.get("tests") or [])
        if oid.startswith("edit.subentity."):
            assert "test_m08g_handlers.py" in tests, oid
        else:
            assert "test_m08kc_handlers.py" in tests, oid


def test_wave4x_subentity_writes_are_staged_only():
    ops = _ops_by_id()
    for oid in ("edit.subentity.add_paths", "edit.subentity.delete_paths", "edit.subentity.transform"):
        wl = ops[oid]["write_level"]
        assert wl["default_write_mode"] == "write_copy", oid
        assert wl["allowed_write_modes"] == ["write_copy"], oid
        assert wl["original_write_default"] is False, oid


def test_wave4x_assocsurface_topology_is_read_safe():
    op = _ops_by_id()["inspect.assocsurface.topology"]
    assert op["policy"]["agent_exposed"] is True
    assert op["policy"]["risk_class"] == "read_safe"
    assert op["policy"]["runtime_behavior"] == "implemented_read_only_or_policy_gated"
