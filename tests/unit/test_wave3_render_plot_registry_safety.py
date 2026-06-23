import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "config" / "operations.v2.json"


def _ops():
    data = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    return {op["id"]: op for op in data["operations"]}


def test_render_layout_has_real_visual_report_handler():
    op = _ops()["render.layout"]
    assert op["status"] == "implemented"
    handler = op["handler"]
    assert handler["router_lane"] == "ARIADNE_CAD_JOB"
    assert handler["dispatcher_symbol"] == "visual_report.build_visual_report"
    assert handler["python_handler"] == "tools/visual_report.py::build_visual_report"
    refs = "\n".join(op.get("evidence_refs") or [])
    tests = "\n".join(op.get("tests") or [])
    assert "tools/visual_report.py" in refs
    assert "tests/unit/test_visual_report.py" in tests


def test_plot_ops_are_not_fake_implemented():
    for oid in ["plot.config.settings", "plot.engine.run"]:
        op = _ops()[oid]
        assert op["status"] == "blocked", oid
        assert op["implementation_strategy"] == "hard_blocked", oid
        reason = op.get("blocked_reason") or ""
        assert reason.startswith(("SAFETY_FORBIDDEN:", "HOST_UNAVAILABLE:")), (oid, reason)
        assert "reports/WAVE3_RENDER_PLOT_REAUDIT.md" in "\n".join(op.get("evidence_refs") or []), oid
