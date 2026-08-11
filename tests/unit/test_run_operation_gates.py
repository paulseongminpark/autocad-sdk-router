"""M10 P1 — cad run_operation safety-gate tests (no accoreconsole needed).

These exercise the allow-list + write-mode governance that must refuse BEFORE
any native job runs. The "actually executes an implemented op headless" proof is
a separate CADOS_LIVE smoke (needs accoreconsole)."""
import hashlib
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


def test_args_operation_cannot_bypass_the_registry_allow_list(monkeypatch, tmp_path):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"synthetic read-only gate probe")
    runner_calls = []

    def unexpected_runner_call(*args, **kwargs):
        runner_calls.append((args, kwargs))
        raise AssertionError("reserved operation override reached the native runner")

    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", unexpected_runner_call)
    cad = cadctl.Cad()
    cad.staging_golden = tmp_path / "staging"

    result = cad.run_operation(
        "inspect.database.graph",
        args={"operation": "extend.deep_native.firing_selftest"},
        dwg_path=str(source),
        out_dir=str(tmp_path / "out"),
    )

    assert result["status"] == "blocked"
    assert result["executed"] is False
    assert result["operation"] == "inspect.database.graph"
    assert "reserved" in result["reason"].lower()
    assert runner_calls == []


def test_normal_args_keep_the_allow_list_operation_and_reach_the_runner(
    monkeypatch, tmp_path
):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"synthetic read-only normal-args probe")
    captured = []

    def fake_runner(staged_dwg, run_dir, operation, *, job_path=None, **kwargs):
        staged_result = tmp_path / "router-result.dwg"
        staged_result.write_bytes(Path(staged_dwg).read_bytes())
        baseline_sha = hashlib.sha256(Path(staged_dwg).read_bytes()).hexdigest()
        result_sha = hashlib.sha256(staged_result.read_bytes()).hexdigest()
        native_result_path = tmp_path / "native-result.json"
        native_result_path.write_text(json.dumps({
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": operation,
            "status": "ok",
            "result": {},
        }), encoding="utf-8")
        write_mode = kwargs.get("write_mode", "read")
        captured.append(
            {
                "operation": operation,
                "job": json.loads(Path(job_path).read_text(encoding="utf-8")),
            }
        )
        return {
            "exit_code": 0,
            "staged_used": str(staged_result),
            "result_json": str(native_result_path),
            "stdout_path": None,
            "stderr_path": None,
            "result": {"status": "ok"},
            "execution": {
                "router_schema": "ariadne.autocad_router_run.v2",
                "router_status": "PASS",
                "executed_route": "dwg_truth_autocad",
                "process_exit_code": 0,
                "engine_exit_code": 0,
                "engine_output_exit_code": 0,
                "timed_out": False,
                "launch_error": None,
                "executed": True,
                "status": "ok",
                "native_status": "ok",
                "native_schema": "ariadne.autocad_native_job_result.v1",
                "native_engine": "native_objectarx",
                "native_operation": operation,
                "native_result_source": "file",
                "native_result_is_object": True,
                "native_error_code": None,
                "native_result_path": str(native_result_path.resolve()),
                "native_result_sha256": hashlib.sha256(
                    native_result_path.read_bytes()
                ).hexdigest(),
                "result_kind": "router_working_copy",
                "result_path": str(staged_result.resolve()),
                "operation": operation,
                "write_mode": write_mode,
                "input_kind": "staged_copy",
                "request_input": str(Path(staged_dwg).resolve()),
                "original_input": str(Path(staged_dwg).resolve()),
                "input": str(staged_result.resolve()),
                "working_sha256_before": baseline_sha,
                "working_sha256_after": result_sha,
                "save_command_issued": write_mode == "write_copy",
                "limitation_codes": [],
            },
            "error": None,
        }

    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", fake_runner)
    cad = cadctl.Cad()
    cad.staging_golden = tmp_path / "staging"

    result = cad.run_operation(
        "inspect.database.graph",
        args={"limit": 5},
        dwg_path=str(source),
        out_dir=str(tmp_path / "out"),
    )

    assert result["status"] == "ok"
    assert result["executed"] is True
    assert captured == [
        {
            "operation": "inspect.database.graph",
            "job": {
                "limit": 5,
                "operation": "inspect.database.graph",
                "input_path": str(source.resolve()),
            },
        }
    ]
