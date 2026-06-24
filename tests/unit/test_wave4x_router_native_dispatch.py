#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WAVE4X router dispatch guard.

Ensures the router's native cad-job gate is no longer frozen to the original P1
list only: implemented registry ops explicitly marked with router_lane=
ARIADNE_NATIVE_JOB must route to the native job path.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PS1 = ROOT / "tools" / "autocad-router.ps1"
REG = ROOT / "config" / "operations.v2.json"


def test_router_native_gate_uses_registry_lane_binding():
    src = PS1.read_text(encoding="utf-8-sig")
    assert "function Test-NativeP1CadJobOperation" in src
    assert "config\\operations.v2.json" in src
    assert "router_lane" in src
    assert "ARIADNE_NATIVE_JOB" in src


def test_wave4x_native_ops_are_marked_for_registry_driven_native_dispatch():
    import json
    ops = {
        op["id"]: op
        for op in json.loads(REG.read_text(encoding="utf-8-sig"))["operations"]
    }
    for oid in (
        "write.dictionary.set",
        "write.object.create_ext_dict",
        "repair.assocdata.audit",
        "edit.assocdata.xref",
    ):
        op = ops[oid]
        assert op["status"] == "implemented", oid
        assert op["handler"]["router_lane"] == "ARIADNE_NATIVE_JOB", oid
