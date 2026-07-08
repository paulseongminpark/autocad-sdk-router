"""W5-TMPL wiring tests for the agent-facing command-template surface.

These tests stay offline: accoreconsole resolution and subprocess execution are
mocked, and only a temp fake DWG is used as the read-only original.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import cadagent_mcp  # noqa: E402
import cadctl  # noqa: E402
import command_template_engine as cte  # noqa: E402


def _fake_dwg(tmp_path: Path) -> Path:
    dwg = tmp_path / "original.dwg"
    dwg.write_bytes(b"FAKE_DWG_BYTES_FOR_TEMPLATE_WIRING")
    return dwg


def _install_fake_accoreconsole(monkeypatch, tmp_path: Path, calls: list[dict]):
    monkeypatch.setattr(cte, "STAGING_DIR", tmp_path / "staging")
    monkeypatch.setattr(cte, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(cte, "resolve_engine", lambda: "fake_accoreconsole.exe")

    def fake_run(cmd, cwd=None, stdout=None, stderr=None, timeout=None):
        calls.append({"cmd": [str(part) for part in cmd], "cwd": cwd, "timeout": timeout})
        if stdout is not None:
            stdout.write(
                "\uc804\uccb4 0\uac74\uc758 \uc624\ub958\ub97c "
                "\ucc3e\uc544\uc11c 0\uac74\uc774 \uc218\uc815\ub428\n"
                .encode("utf-8")
            )
        if stderr is not None:
            stderr.write(b"")
        scr_path = Path(cmd[cmd.index("/s") + 1])
        (scr_path.parent / "entity_count_before.txt").write_text("7\n", encoding="ascii")
        (scr_path.parent / "entity_count_after.txt").write_text("7\n", encoding="ascii")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cte.subprocess, "run", fake_run)


def test_valid_template_dispatches_through_cad_run_command_template(monkeypatch, tmp_path):
    dwg = _fake_dwg(tmp_path)
    calls = []
    _install_fake_accoreconsole(monkeypatch, tmp_path, calls)

    env = cadctl.Cad().run_command_template(
        "maintenance.drawing.audit",
        {"fix_answer": "Y"},
        dwg=str(dwg),
    )

    assert env["schema"] == "ariadne.cadctl.run_command_template.v1"
    assert env["template_id"] == "maintenance.drawing.audit"
    assert env["executed"] is True
    assert env["status"] == "ok"
    assert env["staged_copy"]
    assert env["original_unchanged"] is True
    assert env["stdout"]
    assert calls, "accoreconsole subprocess should be invoked for a valid template"


def test_timeout_sec_is_threaded_to_subprocess(monkeypatch, tmp_path):
    """WHY (finding 5): a caller's timeout_sec must reach subprocess.run's timeout= kwarg,
    not be silently dropped at the engine's fixed 120s default."""
    dwg = _fake_dwg(tmp_path)
    calls = []
    _install_fake_accoreconsole(monkeypatch, tmp_path, calls)

    # explicit budget is forwarded end-to-end
    cadctl.Cad().run_command_template(
        "maintenance.drawing.audit", {"fix_answer": "Y"}, dwg=str(dwg), timeout_sec=47)
    assert calls[-1]["timeout"] == 47

    # no override falls back to the engine's documented 120s default
    cadctl.Cad().run_command_template(
        "maintenance.drawing.audit", {"fix_answer": "Y"}, dwg=str(dwg))
    assert calls[-1]["timeout"] == 120.0


def test_staged_path_slot_is_autofilled_with_staged_copy(monkeypatch, tmp_path):
    """WHY (cert wave 2): run_template must stage BEFORE rendering and auto-fill a
    staged_path slot with its own staged copy, closing the documented RECOVER wiring
    gap (the fresh timestamped path is unknowable to a caller). The rendered .scr must
    carry the staged path and the result envelope must record the effective args."""
    dwg = _fake_dwg(tmp_path)
    calls = []
    _install_fake_accoreconsole(monkeypatch, tmp_path, calls)

    env = cte.run_template(
        "maintenance.drawing.recover", {}, str(dwg),
        write_mode="write_copy", _force_unverified=True,
    )

    assert env["status"] == "ok"
    details = env["details"]
    staged = details["staged_input"]
    # the auto-filled effective args are recorded (evidence of what actually ran)
    eff_args = env["result"]["args"]
    assert eff_args.get("recover_target_path"), env["result"]
    assert Path(eff_args["recover_target_path"]).resolve() == Path(staged).resolve()
    # the rendered .scr actually carries the staged path on the RECOVER answer line
    scr_path = Path(details["scr_path"])
    scr_lines = scr_path.read_text(encoding="ascii").splitlines()
    ridx = scr_lines.index("RECOVER")
    assert Path(scr_lines[ridx + 1]).resolve() == Path(staged).resolve()


def test_mcp_tool_delegates_with_ok_result_envelope(monkeypatch, tmp_path):
    dwg = _fake_dwg(tmp_path)
    calls = []
    _install_fake_accoreconsole(monkeypatch, tmp_path, calls)

    resp = cadagent_mcp.handle_rpc({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "cad.run_command_template",
            "arguments": {
                "template_id": "maintenance.drawing.audit",
                "slots": {"fix_answer": "Y"},
                "dwg": str(dwg),
            },
        },
    })

    payload = json.loads(resp)["result"]["structuredContent"]
    assert payload["ok"] is True
    assert payload["result"]["template_id"] == "maintenance.drawing.audit"
    assert payload["result"]["executed"] is True


def test_unknown_template_id_is_refused_before_execution(monkeypatch, tmp_path):
    dwg = _fake_dwg(tmp_path)
    calls = []

    def fail_run(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("unknown template must not execute")

    monkeypatch.setattr(cte.subprocess, "run", fail_run)

    env = cadctl.Cad().run_command_template("no.such.template", {}, dwg=str(dwg))

    assert env["status"] == "not_found"
    assert env["executed"] is False
    assert env["staged_copy"] is None
    assert calls == []


def test_hostile_slot_value_rejected_before_execution(monkeypatch, tmp_path):
    dwg = _fake_dwg(tmp_path)
    calls = []
    monkeypatch.setattr(cte, "resolve_engine", lambda: "fake_accoreconsole.exe")

    def fail_run(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("hostile slot must be rejected before execution")

    monkeypatch.setattr(cte.subprocess, "run", fail_run)

    env = cadctl.Cad().run_command_template(
        "maintenance.drawing.audit",
        {"fix_answer": "Y; QUIT"},
        dwg=str(dwg),
    )

    assert env["status"] == "blocked"
    assert env["executed"] is False
    assert env["staged_copy"] is None
    assert env["error"]["code"] == "INJECTION_REJECTED"
    assert calls == []


def test_template_execution_uses_staged_copy_and_leaves_original_unchanged(monkeypatch, tmp_path):
    dwg = _fake_dwg(tmp_path)
    original_bytes = dwg.read_bytes()
    original_sha = cte.sha256_file(dwg)
    calls = []
    _install_fake_accoreconsole(monkeypatch, tmp_path, calls)

    env = cadctl.Cad().run_command_template(
        "maintenance.drawing.audit",
        {"fix_answer": "Y"},
        dwg=str(dwg),
    )

    cmd = calls[0]["cmd"]
    accore_input = Path(cmd[cmd.index("/i") + 1]).resolve()
    staged_copy = Path(env["staged_copy"]).resolve()
    assert accore_input == staged_copy
    assert accore_input != dwg.resolve()
    assert staged_copy.is_file()
    assert dwg.read_bytes() == original_bytes
    assert cte.sha256_file(dwg) == original_sha
    assert env["original_unchanged"] is True
