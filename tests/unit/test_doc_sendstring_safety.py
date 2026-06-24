#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wave4X Loader/Doc R2 doc.sendstring safety tests."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "operations.v2.json"
OPS_REPORT = ROOT / "reports" / "tickets" / "WAVE4X_LOADER_DOC_R2_OPS.json"


def _registry() -> dict[str, dict]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    return {op["id"]: op for op in data["operations"]}


def test_doc_sendstring_is_blocked_internal_only_and_non_agent_exposed():
    op = _registry()["doc.sendstring"]
    assert op["status"] == "blocked"
    assert op["implementation_strategy"] == "hard_blocked"
    assert op["policy"]["agent_exposed"] is False
    assert op["policy"]["risk_class"] == "raw_command"
    assert op["policy"]["runtime_behavior"] == "blocked_internal_only_raw_command_surface"
    assert op["handler"]["dispatcher_symbol"] is None
    assert "SAFETY_FORBIDDEN" in op["blocked_reason"]
    assert "raw command" in op["blocked_reason"].lower()
    assert any("WAVE4X_LOADER_DOC_R2" in ref for ref in op.get("evidence_refs", []))


def test_doc_sendstring_report_decision_is_not_implemented_as_agent_surface():
    assert OPS_REPORT.exists()
    data = json.loads(OPS_REPORT.read_text(encoding="utf-8"))
    row = next(row for row in data["operations"] if row["operation"] == "doc.sendstring")
    assert row["final_state"] == "hard_blocked"
    assert row["decision"] == "not_agent_exposed_raw_command_surface"
    assert row["agent_exposed"] is False
