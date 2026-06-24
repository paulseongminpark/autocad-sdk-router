#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wave4X Pane 2 loader/doc/command safe implementation tests."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INC = REPO / "src" / "Ariadne.AcadNative" / "families" / "m08n_handlers.inc"
REGISTRY = REPO / "config" / "operations.v2.json"

SAFE_IMPLEMENTED = {
    "module.command.lookup",
    "module.command.remove_group",
    "module.load",
    "module.load.acad_rx",
    "module.load.by_app",
    "module.load.demand_register",
    "module.unload",
}


def _src() -> str:
    return INC.read_text(encoding="utf-8", errors="replace")


def _code_only(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def _hasop_ops(src: str) -> set[str]:
    m = re.search(r"static bool m08nHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "m08nHasOp not found"
    return set(re.findall(r'op == "([^"]+)"', m.group(1)))


def _registry() -> dict[str, dict]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    return {op["id"]: op for op in data["operations"]}


def test_safe_loader_doc_ops_are_native_dispatched():
    src = _src()
    hasop = _hasop_ops(src)
    missing = sorted(SAFE_IMPLEMENTED - hasop)
    assert missing == []
    for op in SAFE_IMPLEMENTED:
        assert f'op == "{op}"' in src
    assert "ARIADNE_W4X_LOADER_DOC" in src
    assert "demand_load_plan" in src
    assert "raw_command_agent_surface" in src


def test_safe_loader_doc_ops_are_registry_implemented():
    ops = _registry()
    for op_id in sorted(SAFE_IMPLEMENTED):
        op = ops[op_id]
        assert op["status"] == "implemented", op_id
        assert op["handler"]["dispatcher_symbol"] == "m08nDispatch", op_id
        assert op["implementation_strategy"] == "implemented_v1", op_id
        refs = "\n".join(op.get("evidence_refs") or [])
        assert "reports/tickets/WAVE4X_LOADER_DOC.md" in refs, op_id
        tests = "\n".join(op.get("tests") or [])
        assert "tests/unit/test_m08_loader_doc.py" in tests, op_id


def test_safe_loader_doc_source_does_not_expose_raw_or_arbitrary_load_execution():
    code = _code_only(_src())
    banned = [
        r"\bacedCommand\b",
        r"\bacedCmd\b",
        r"\bacedInvoke\b",
        r"\bacrxLoadModule\s*\(",
        r"\bacrxLoadApp\s*\(",
        r"\bacrxUnloadModule\s*\(",
        r"\bacrxUnloadApp\s*\(",
        r"\bRegSetValue",
        r"\bSHSetValue",
        r"sendStringToExecute\s*\(",
    ]
    for pat in banned:
        assert re.search(pat, code) is None, pat


def test_loader_doc_handlers_are_status_or_bounded_cleanup_only():
    src = _src()
    for token in [
        "lookupGlobalCmd",
        "removeGroup(_T(\"ARIADNE_W4X_LOADER_DOC\"))",
        "GetModuleHandleW",
        "acrxDynamicLinker",
        "acad_rx_checked",
        "demand_load_registry_mutated",
        "module_unload_invoked",
    ]:
        assert token in src
