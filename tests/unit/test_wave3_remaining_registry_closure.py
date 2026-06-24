import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "config" / "operations.v2.json"

EXPECTED_BLOCKED_AFTER_REAUDIT = {
    "ui.subentity.highlight",
    "automate.com.send_command",
    "embed.ole.frame",
    "module.command.remove_group",
    "module.entrypoint.define",
    "module.entrypoint.dispatch",
    "module.lifecycle.init",
    "module.lifecycle.on_load_dwg",
    "module.lifecycle.on_ole_unload",
    "module.lifecycle.on_unload_dwg",
    "module.lifecycle.other",
    "module.lifecycle.unload",
    "module.load",
    "module.load.acad_rx",
    "module.load.by_app",
    "module.unload",
}

EXPECTED_IMPLEMENTED_AFTER_WAVE4X = {
    "automate.com.get_app",
    "automate.com.get_document",
    "automate.com.get_for_command",
    "automate.com.get_winapp",
    "automate.com.wrapper_for_object",
    "module.load.lisp",
}

ALLOWED_BLOCKER_CODES = {
    "SDK_NOT_EXPOSED",
    "HOST_UNAVAILABLE",
    "LICENSE_UNAVAILABLE",
    "SAFETY_FORBIDDEN",
    "OBJECT_ENABLER_REQUIRED",
    "ORIGINAL_WRITE_FORBIDDEN",
}


def _operations():
    data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    return {op["id"]: op for op in data["operations"]}


def test_remaining_wave3_catalogued_ops_are_closed_after_reaudit():
    ops = _operations()
    still_open = [
        oid for oid in EXPECTED_BLOCKED_AFTER_REAUDIT
        if ops[oid]["status"] in {"catalogued", "stub", "unknown", "deferred"}
    ]
    assert still_open == []


def test_remaining_wave3_blocks_have_accepted_codes_and_evidence():
    ops = _operations()
    for oid in sorted(EXPECTED_BLOCKED_AFTER_REAUDIT):
        op = ops[oid]
        assert op["status"] == "blocked", oid
        reason = op.get("blocked_reason") or ""
        code = reason.split(":", 1)[0]
        assert code in ALLOWED_BLOCKER_CODES, (oid, reason)
        evidence = "\n".join(op.get("evidence_refs") or [])
        assert "reports/WAVE3_REMAINING_HARDBLOCK_REAUDIT.md" in evidence, oid
        assert op.get("implementation_strategy") == "hard_blocked", oid
        assert op.get("evidence_required") == "blocker_ref_and_evidence", oid


def test_wave4x_reopened_safe_fallback_ops_are_implemented():
    ops = _operations()
    for oid in sorted(EXPECTED_IMPLEMENTED_AFTER_WAVE4X):
        op = ops[oid]
        assert op["status"] == "implemented", oid
        evidence = "\n".join(op.get("evidence_refs") or [])
        assert "reports/tickets/WAVE4X_FALLBACK.md" in evidence, oid
        assert op.get("handler", {}).get("dispatcher_symbol") == "Invoke-SafeFallbackOperation", oid
        if oid == "module.load.lisp":
            assert op.get("handler", {}).get("router_lane") == "ARIADNE_CAD_JOB", oid
            assert op.get("handler", {}).get("execution_host_class") == "coreconsole", oid
        else:
            assert op.get("handler", {}).get("router_lane") == "full_autocad", oid
            assert op.get("handler", {}).get("execution_host_class") == "full_autocad", oid


def test_module_command_flags_was_reversed_to_implemented():
    op = _operations()["module.command.flags"]
    assert op["status"] == "implemented"
    assert op["handler"]["dispatcher_symbol"] == "m08nDispatch"
    evidence = "\n".join(op.get("evidence_refs") or [])
    assert "tests/unit/test_m08n_handlers.py::TestM08NHandlers::test_module_command_flags_is_read_only_inventory" in evidence
    assert "reports/WAVE3_REMAINING_HARDBLOCK_REAUDIT.md#module.command.flags" in evidence


def test_inspect_subentity_color_was_reversed_to_implemented():
    op = _operations()["inspect.subentity.color"]
    assert op["status"] == "implemented"
    assert op["handler"]["dispatcher_symbol"] == "m08dDispatch"
    evidence = "\n".join(op.get("evidence_refs") or [])
    assert "tests/unit/test_m08d_handlers.py::TestM08DHandlers::test_subentity_color_read_uses_real_apis" in evidence
    assert "reports/WAVE3_REMAINING_HARDBLOCK_REAUDIT.md#inspect.subentity.color" in evidence


def test_subentity_writes_were_reopened_to_implemented():
    ops = _operations()
    for oid in ("edit.subentity.add_paths", "edit.subentity.delete_paths", "edit.subentity.transform"):
        op = ops[oid]
        assert op["status"] == "implemented", oid
        assert op["handler"]["dispatcher_symbol"] == "m08gDispatch", oid
        evidence = "\n".join(op.get("evidence_refs") or [])
        assert "WAVE4X_SUBENTITY_BREP" in evidence, oid
