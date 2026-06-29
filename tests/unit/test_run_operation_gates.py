"""M10 P1 — cad run_operation safety-gate tests (no accoreconsole needed).

These exercise the allow-list + write-mode governance that must refuse BEFORE
any native job runs. The "actually executes an implemented op headless" proof is
a separate CADOS_LIVE smoke (needs accoreconsole)."""
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
import cadctl  # noqa: E402

_REG = _ROOT / "config" / "operations.v2.json"


def _ops():
    return json.loads(_REG.read_text(encoding="utf-8-sig")).get("operations", [])


def _first(status):
    for o in _ops():
        if o.get("status") == status:
            return o.get("id") or o.get("operation")
    return None


def test_run_operation_exists():
    assert hasattr(cadctl.Cad, "run_operation")
    assert hasattr(cadctl, "run_operation")


def test_unknown_op_refused(tmp_path):
    r = cadctl.Cad().run_operation("nonexistent.op.xyz", dwg_path=None, out_dir=str(tmp_path))
    assert r["status"] == "not_found"
    assert r["executed"] is False


def test_blocked_op_refused(tmp_path):
    blocked = _first("blocked")
    assert blocked, "registry must contain at least one blocked op"
    r = cadctl.Cad().run_operation(blocked, dwg_path=None, out_dir=str(tmp_path))
    assert r["status"] == "blocked"
    assert r["executed"] is False
    assert r["registry_operation_status"] == "blocked"


def test_write_original_always_refused(tmp_path):
    impl = _first("implemented")
    assert impl
    r = cadctl.Cad().run_operation(impl, write_mode="write_original",
                                   dwg_path=None, out_dir=str(tmp_path))
    assert r["status"] == "blocked"
    assert r["executed"] is False
    assert "write_original" in r["reason"]


def test_implemented_requires_dwg(tmp_path):
    impl = _first("implemented")
    assert impl
    r = cadctl.Cad().run_operation(impl, dwg_path=None, out_dir=str(tmp_path))
    assert r["status"] == "blocked"
    assert r["executed"] is False
    assert "dwg_path" in r["reason"]


def test_bad_write_mode_refused(tmp_path):
    impl = _first("implemented")
    r = cadctl.Cad().run_operation(impl, write_mode="totally_invalid_mode",
                                   dwg_path=None, out_dir=str(tmp_path))
    assert r["status"] == "blocked"
    assert r["executed"] is False
    assert "allowed_write_modes" in r["reason"]
