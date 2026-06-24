#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fast B registry and pump assertions for live/UI and staged policy closure."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "config" / "operations.v2.json"
NATIVE = REPO / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"


def _ops() -> dict[str, dict]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    return {op["id"]: op for op in data["operations"]}


def test_live_ui_ops_are_implemented_with_safe_contracts():
    ops = _ops()
    for op_id, dispatcher in {
        "editor.toolpalette.tool_execute": "m08nDispatch",
        "ui.subentity.highlight": "m08dDispatch",
    }.items():
        op = ops[op_id]
        assert op["status"] == "implemented", op_id
        assert op["handler"]["dispatcher_symbol"] == dispatcher, op_id
        assert op["implementation_strategy"] == "implemented_v1", op_id
        assert op["policy"]["agent_exposed"] is True, op_id
        refs = "\n".join(op.get("evidence_refs") or [])
        assert "WAVE4X_FAST_B_LIVE_UI_PROOF_R2" in refs, op_id


def test_live_apply_patch_stays_deprecated_and_points_to_staged_governor():
    op = _ops()["live.apply_patch"]
    assert op["status"] == "deprecated"
    assert op["implementation_strategy"] == "deprecated_safe_replacement"
    assert op["evidence_required"] == "replacement_route_and_evidence"
    assert op["replacement_ref"] == "apply.patch + tools/patch_engine.py::apply_native_staged"
    assert op["write_level"]["allowed_write_modes"] == ["read"]
    refs = "\n".join(op.get("evidence_refs") or [])
    assert "WAVE4X_FAST_B_LIVE_APPLY_POLICY_R2" in refs


def test_pump_safe_dispatch_whitelists_fast_b_attended_ops():
    src = NATIVE.read_text(encoding="utf-8", errors="replace")
    assert "static bool tryPumpSafeDispatch" in src
    assert "tryPumpSafeDispatch(op, ctx, fr)" in src
    assert 'r << fr.str();' in src
    for token in [
        'op == "plot.config.settings"',
        'op == "plot.engine.run"',
        'op == "ui.subentity.highlight"',
        'op == "editor.toolpalette.tool_execute"',
        '"fast_b_safe_attended:',
        '\\"supported_ops\\":[',
    ]:
        assert token in src
