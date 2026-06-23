#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wave4X Pane 2 lifecycle/doc hard-block evidence tests."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "config" / "operations.v2.json"

STILL_HARD_BLOCKED = {
    "doc.sendstring": "SAFETY_FORBIDDEN",
    "module.entrypoint.define": "SDK_NOT_EXPOSED",
    "module.entrypoint.dispatch": "HOST_UNAVAILABLE",
    "module.lifecycle.init": "HOST_UNAVAILABLE",
    "module.lifecycle.on_load_dwg": "HOST_UNAVAILABLE",
    "module.lifecycle.on_unload_dwg": "HOST_UNAVAILABLE",
    "module.lifecycle.other": "HOST_UNAVAILABLE",
    "module.lifecycle.unload": "HOST_UNAVAILABLE",
}


def _registry() -> dict[str, dict]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    return {op["id"]: op for op in data["operations"]}


def test_lifecycle_and_doc_raw_surfaces_remain_hard_blocked_with_wave4x_evidence():
    ops = _registry()
    for op_id, code in sorted(STILL_HARD_BLOCKED.items()):
        op = ops[op_id]
        assert op["status"] == "blocked", op_id
        reason = op.get("blocked_reason") or ""
        assert reason.startswith(code + ":"), (op_id, reason)
        assert op.get("implementation_strategy") == "hard_blocked", op_id
        refs = "\n".join(op.get("evidence_refs") or [])
        assert "reports/tickets/WAVE4X_LOADER_DOC.md" in refs, op_id
        tests = "\n".join(op.get("tests") or [])
        assert "tests/unit/test_m08_doc_lifecycle.py" in tests, op_id


def test_no_forbidden_final_states_in_pane2_claims():
    forbidden = {"catalogued", "stub", "unknown", "deferred", "future_version", "v1_target_false_escape"}
    claim_ops = set(STILL_HARD_BLOCKED)
    claim_ops.update({
        "module.command.lookup",
        "module.command.remove_group",
        "module.load",
        "module.load.acad_rx",
        "module.load.by_app",
        "module.load.demand_register",
        "module.unload",
    })
    ops = _registry()
    bad = sorted((op_id, ops[op_id]["status"]) for op_id in claim_ops if ops[op_id]["status"] in forbidden)
    assert bad == []
