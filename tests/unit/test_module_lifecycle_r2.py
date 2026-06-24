#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wave4X Loader/Doc R2 module lifecycle evidence tests."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "operations.v2.json"
M08N = ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08n_handlers.inc"
OPS_REPORT = ROOT / "reports" / "tickets" / "WAVE4X_LOADER_DOC_R2_OPS.json"

MODULE_LIFECYCLE_TARGETS = [
    "module.entrypoint.define",
    "module.entrypoint.dispatch",
    "module.lifecycle.init",
    "module.lifecycle.on_load_dwg",
    "module.lifecycle.on_unload_dwg",
    "module.lifecycle.other",
    "module.lifecycle.unload",
]


def _registry() -> dict[str, dict]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    return {op["id"]: op for op in data["operations"]}


def _hasop_ops() -> set[str]:
    src = M08N.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"static bool m08nHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert match, "m08nHasOp not found"
    return set(re.findall(r'op == "([^"]+)"', match.group(1)))


def test_lifecycle_targets_are_native_evidence_status_handlers():
    registry = _registry()
    hasop = _hasop_ops()
    for op_id in MODULE_LIFECYCLE_TARGETS:
        op = registry[op_id]
        assert op["status"] == "implemented", op_id
        assert op["handler"]["dispatcher_symbol"] == "m08nDispatch", op_id
        assert op["handler"]["router_lane"] == "ARIADNE_NATIVE_JOB", op_id
        assert op["policy"]["runtime_behavior"] == "lifecycle_evidence_status_only", op_id
        assert op["policy"]["agent_exposed"] is True, op_id
        assert op["policy"]["risk_class"] == "read_safe", op_id
        assert op_id in hasop, op_id
        assert any("WAVE4X_LOADER_DOC_R2" in ref for ref in op.get("evidence_refs", [])), op_id


def test_lifecycle_dispatch_is_not_synthetic_host_callback_dispatch():
    src = M08N.read_text(encoding="utf-8", errors="replace")
    for token in [
        "m08nModuleLifecycleEvidence",
        "actual_lifecycle_callback_invoked",
        "synthetic_loader_message_dispatched",
        "lifecycle_evidence_status_only",
    ]:
        assert token in src
    for forbidden in [
        "On_kInitAppMsg(",
        "On_kLoadDwgMsg(",
        "On_kUnloadDwgMsg(",
        "On_kUnloadAppMsg(",
        "acrxEntryPoint(",
    ]:
        assert forbidden not in re.sub(r"//[^\n]*", "", src)


def test_r2_ops_report_covers_all_lifecycle_targets():
    assert OPS_REPORT.exists()
    data = json.loads(OPS_REPORT.read_text(encoding="utf-8"))
    rows = {row["operation"]: row for row in data["operations"]}
    for op_id in MODULE_LIFECYCLE_TARGETS:
        assert rows[op_id]["final_state"] == "implemented"
        assert rows[op_id]["decision"] == "native_lifecycle_evidence_status_only"
