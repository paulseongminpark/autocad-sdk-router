"""Public execution-provenance contract for ``Cad.run_operation``.

These tests deliberately stop at the Python/router seam.  They make the fake
router report the same facts the PowerShell entry point reports, then require
``cadctl`` to bind those facts to the operation it authorized.  No CAD process
is launched.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import cadctl  # noqa: E402
import run_job  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _router_result(
    tmp_path: Path,
    staged_dwg: str,
    *,
    authorized_operation: str,
    authorized_write_mode: str,
    actual_operation: str | None = None,
    actual_write_mode: str | None = None,
    engine_status: str | None = "ok",
    engine_exit_code: int | None = 0,
    process_exit_code: int | None = 0,
    native_status: str | None = "ok",
    native_schema: str | None = "ariadne.autocad_native_job_result.v1",
    native_engine: str | None = "native_objectarx",
    native_operation: str | None = None,
    native_result_source: str | None = "file",
    native_result_is_object: bool | None = True,
    native_error_code: str | None = None,
    result_kind: str | None = "router_working_copy",
    native_output_path: Path | None = None,
    hardlink_result: bool = False,
    outside_hardlink_result: bool = False,
    include_result: bool = True,
    request_input_override: str | None = None,
) -> dict:
    baseline = Path(staged_dwg)
    result_path = tmp_path / "router" / "input.dwg"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    if hardlink_result:
        os.link(baseline, result_path)
    elif outside_hardlink_result:
        outside = tmp_path / "outside-protected.dwg"
        outside.write_bytes(b"outside physical generation")
        os.link(outside, result_path)
    else:
        result_path.write_bytes(baseline.read_bytes())
    result_json = tmp_path / "router-result.json"
    if native_output_path is not None:
        native_output_path.parent.mkdir(parents=True, exist_ok=True)
        native_output_path.write_bytes(b"native output artifact")
        result_kind = "native_output"
        result_payload: object = {
            "written": True,
            "output_path": str(native_output_path),
        }
        canonical_result_path = native_output_path
    else:
        result_payload = {} if native_result_is_object is not False else []
        canonical_result_path = result_path
    native_result = {
        "schema": native_schema,
        "engine": native_engine,
        "operation": native_operation or actual_operation or authorized_operation,
        "status": native_status,
        "result": result_payload,
    }
    if native_error_code is not None:
        native_result["error_code"] = native_error_code
    result_json.write_text(json.dumps(native_result), encoding="utf-8")

    execution = {
        "router_schema": "ariadne.autocad_router_run.v2",
        "router_status": "PASS",
        "executed_route": "dwg_truth_autocad",
        "process_exit_code": process_exit_code,
        "engine_exit_code": engine_exit_code,
        "engine_output_exit_code": engine_exit_code,
        "timed_out": False,
        "launch_error": None,
        "executed": True,
        "status": engine_status,
        "native_status": native_status,
        "native_schema": native_schema,
        "native_engine": native_engine,
        "native_operation": native_result["operation"],
        "native_result_source": native_result_source,
        "native_result_is_object": native_result_is_object,
        "native_error_code": native_error_code,
        "native_result_path": str(result_json.resolve()),
        "native_result_sha256": _sha256(result_json),
        "result_kind": result_kind,
        "result_path": str(canonical_result_path) if include_result else None,
        "operation": actual_operation or authorized_operation,
        "write_mode": actual_write_mode or authorized_write_mode,
        "input_kind": "staged_copy",
        "request_input": request_input_override or str(baseline),
        "original_input": str(baseline),
        "input": str(result_path) if include_result else None,
        "working_sha256_before": _sha256(baseline),
        "working_sha256_after": _sha256(result_path) if include_result else None,
        "save_command_issued": authorized_write_mode == "write_copy",
        "limitation_codes": [],
    }
    engine_output = {
        key: value
        for key, value in execution.items()
        if key not in {
            "router_schema", "router_status", "executed_route", "process_exit_code"
        }
    }
    return {
        "command": ["fake-router"],
        "exit_code": process_exit_code,
        "stdout_path": str(tmp_path / "stdout.txt"),
        "stderr_path": str(tmp_path / "stderr.txt"),
        "envelope": {
            "schema": execution["router_schema"],
            "status": execution["router_status"],
            "executed_route": execution["executed_route"],
            "execution": {
                "engine_exit_code": engine_exit_code,
                "engine_output": engine_output,
            },
        },
        "execution": execution,
        "result_json": str(result_json),
        "result": result_payload if isinstance(result_payload, dict) else None,
        "staged_used": str(canonical_result_path) if include_result else None,
        "timed_out": False,
        "error": None,
    }


def _run_with_fake(
    monkeypatch,
    tmp_path: Path,
    *,
    staging_golden: Path | None = None,
    **overrides,
) -> dict:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"synthetic immutable source")

    def fake_runner(staged_dwg, run_dir, operation, *, write_mode="read", **kwargs):
        return _router_result(
            tmp_path,
            staged_dwg,
            authorized_operation=operation,
            authorized_write_mode=write_mode,
            **overrides,
        )

    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", fake_runner)
    cad = cadctl.Cad()
    cad.staging_golden = staging_golden or (tmp_path / "staging")
    return cad.run_operation(
        "inspect.database.graph",
        write_mode="read",
        dwg_path=str(source),
        out_dir=str(tmp_path / "out"),
    )


def test_matching_execution_has_one_bound_canonical_receipt(monkeypatch, tmp_path):
    env = _run_with_fake(monkeypatch, tmp_path)

    assert env["schema"] == "ariadne.cadctl.run_operation.v1"
    assert env["status"] == "ok"
    assert env["executed"] is True
    receipt = env["execution_receipt"]
    assert receipt["schema"] == "ariadne.cadctl.operation_execution_receipt.v1"
    assert receipt["verification"]["bound"] is True
    assert receipt["verification"]["outcome_successful"] is True
    assert receipt["authorization"]["operation"] == "inspect.database.graph"
    assert receipt["execution"]["operation"] == "inspect.database.graph"
    assert receipt["matches"]["operation"] is True
    assert receipt["matches"]["write_mode"] is True
    assert receipt["matches"]["router_input_to_baseline"] is True
    assert receipt["matches"]["original_unchanged"] is True
    assert receipt["artifacts"]["baseline"]["unchanged"] is True
    assert env["staged_result"] == receipt["artifacts"]["result"]["path"]
    assert env["staged_result_sha256"] == receipt["artifacts"]["result"]["sha256"]


def test_different_reported_operation_is_executed_but_never_ok(monkeypatch, tmp_path):
    env = _run_with_fake(
        monkeypatch,
        tmp_path,
        actual_operation="extend.deep_native.firing_selftest",
    )

    assert env["executed"] is True
    assert env["status"] == "error"
    assert env["execution_receipt"]["verification"]["bound"] is False
    assert env["execution_receipt"]["matches"]["operation"] is False
    assert "OPERATION_MISMATCH" in env["execution_receipt"]["verification"]["failure_codes"]


def test_foreign_native_result_schema_is_never_promoted_to_ok(monkeypatch, tmp_path):
    env = _run_with_fake(
        monkeypatch,
        tmp_path,
        native_schema="foreign.result.v0",
    )

    assert env["status"] != "ok"
    verification = env["execution_receipt"]["verification"]
    assert verification["outcome_successful"] is False
    assert "NATIVE_SCHEMA_MISMATCH" in verification["failure_codes"]


@pytest.mark.parametrize(
    ("overrides", "failure_code"),
    [
        ({"native_engine": "foreign_engine"}, "NATIVE_ENGINE_MISMATCH"),
        ({"native_operation": "wrong.operation"}, "NATIVE_OPERATION_MISMATCH"),
        ({"native_result_source": "inline"}, "NATIVE_RESULT_SOURCE_NOT_FILE"),
        ({"native_result_is_object": False}, "NATIVE_RESULT_NOT_OBJECT"),
        ({"native_error_code": "NATIVE_FAILURE"}, "NATIVE_ERROR_CONTRADICTION"),
    ],
)
def test_unbound_native_result_facts_are_never_promoted_to_ok(
    monkeypatch, tmp_path, overrides, failure_code
):
    env = _run_with_fake(monkeypatch, tmp_path, **overrides)

    assert env["status"] != "ok"
    verification = env["execution_receipt"]["verification"]
    assert verification["outcome_successful"] is False
    assert failure_code in verification["failure_codes"]


def test_save_as_binds_the_authorized_native_output_not_router_working_copy(
    monkeypatch, tmp_path
):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"synthetic immutable source")
    output_path = tmp_path / "out" / "saved.dwg"
    output_path.parent.mkdir(parents=True)

    def fake_runner(staged_dwg, run_dir, operation, *, write_mode="read", **kwargs):
        job = json.loads(Path(kwargs["job_path"]).read_text(encoding="utf-8"))
        private_output_path = Path(job["output_path"])
        assert private_output_path != output_path
        return _router_result(
            tmp_path,
            staged_dwg,
            authorized_operation=operation,
            authorized_write_mode=write_mode,
            native_output_path=private_output_path,
        )

    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", fake_runner)
    cad = cadctl.Cad()
    cad.staging_golden = tmp_path / "staging"

    env = cad.run_operation(
        "transform.database.save_as",
        args={"output_path": str(output_path)},
        write_mode="write_copy",
        dwg_path=str(source),
        out_dir=str(tmp_path / "out"),
    )

    assert env["status"] == "ok"
    assert output_path.exists() is False
    result_path = Path(env["staged_result"])
    assert result_path.name == output_path.name
    result_path.relative_to(output_path.parent)
    assert Path(env["execution_dir"]) in result_path.parents
    receipt = env["execution_receipt"]
    assert receipt["artifacts"]["result"]["kind"] == "native_output"
    assert receipt["artifacts"]["result"]["path"] == str(result_path.resolve())
    assert env["requested_output_path"] == str(output_path.resolve())
    assert env["authorized_native_output_path"] == str(result_path.resolve())


def test_different_reported_write_mode_is_executed_but_never_ok(monkeypatch, tmp_path):
    env = _run_with_fake(
        monkeypatch,
        tmp_path,
        actual_write_mode="write_original",
    )

    assert env["executed"] is True
    assert env["status"] == "error"
    assert env["execution_receipt"]["matches"]["write_mode"] is False
    assert "WRITE_MODE_MISMATCH" in env["execution_receipt"]["verification"]["failure_codes"]


def test_different_reported_router_input_is_never_bound(monkeypatch, tmp_path):
    env = _run_with_fake(
        monkeypatch,
        tmp_path,
        request_input_override=str((tmp_path / "wrong-baseline.dwg").resolve()),
    )

    assert env["status"] == "error"
    verification = env["execution_receipt"]["verification"]
    assert verification["bound"] is False
    assert "ROUTER_INPUT_BASELINE_MISMATCH" in verification["failure_codes"]


def test_result_outside_staging_is_not_opened_or_exposed(monkeypatch, tmp_path):
    env = _run_with_fake(
        monkeypatch,
        tmp_path,
        staging_golden=tmp_path / "allowed" / "staging",
    )

    assert env["status"] == "error"
    assert env["staged_result"] is None
    verification = env["execution_receipt"]["verification"]
    assert verification["bound"] is False
    assert "RESULT_OUTSIDE_STAGING" in verification["failure_codes"]


def test_result_hardlinked_to_baseline_is_never_bound(monkeypatch, tmp_path):
    env = _run_with_fake(monkeypatch, tmp_path, hardlink_result=True)

    assert env["status"] != "ok"
    verification = env["execution_receipt"]["verification"]
    assert verification["bound"] is False
    assert "RESULT_FILE_IDENTITY_COLLISION" in verification["failure_codes"]


def test_result_with_an_unlisted_hardlink_is_never_bound(monkeypatch, tmp_path):
    env = _run_with_fake(
        monkeypatch,
        tmp_path,
        outside_hardlink_result=True,
    )

    assert env["status"] != "ok"
    verification = env["execution_receipt"]["verification"]
    assert verification["bound"] is False
    assert "RESULT_FILE_IDENTITY_COLLISION" in verification["failure_codes"]


def test_native_output_equal_to_original_is_refused_before_router_launch(
    monkeypatch, tmp_path
):
    original = tmp_path / "original.dwg"
    original.write_bytes(b"immutable original")
    original_sha = _sha256(original)
    runner_called = False

    def destructive_runner(*args, **kwargs):
        nonlocal runner_called
        runner_called = True
        original.write_bytes(b"damage that preflight must prevent")
        raise AssertionError("router must not run for an original-output collision")

    cad = cadctl.Cad()
    cad.staging_golden = tmp_path / "staging"
    monkeypatch.setattr(
        cad,
        "_registry_record",
        lambda op_id: {
            "status": "implemented",
            "write_level": {
                "default_write_mode": "write_copy",
                "allowed_write_modes": ["write_copy"],
            },
        },
    )
    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", destructive_runner)

    env = cad.run_operation(
        "transform.database.save_as",
        args={"output_path": str(original.resolve())},
        write_mode="write_copy",
        dwg_path=str(original),
        out_dir=str(tmp_path / "out"),
    )

    assert runner_called is False
    assert _sha256(original) == original_sha
    assert env["executed"] is False
    assert env["status"] == "blocked"
    assert "OUTPUT_PATH_COLLIDES_WITH_ORIGINAL" in env["reason"]


def test_native_output_outside_run_directory_is_refused_before_router_launch(
    monkeypatch, tmp_path
):
    original = tmp_path / "original-a.dwg"
    original.write_bytes(b"immutable source a")
    protected_other = tmp_path / "protected-b.dwg"
    protected_other.write_bytes(b"independent protected drawing b")
    protected_sha = _sha256(protected_other)
    runner_called = False

    def destructive_runner(*args, **kwargs):
        nonlocal runner_called
        runner_called = True
        protected_other.write_bytes(b"damage to drawing b")
        raise AssertionError("router must not write outside its run directory")

    cad = cadctl.Cad()
    cad.staging_golden = tmp_path / "staging"
    monkeypatch.setattr(
        cad,
        "_registry_record",
        lambda op_id: {
            "status": "implemented",
            "write_level": {
                "default_write_mode": "write_copy",
                "allowed_write_modes": ["write_copy"],
            },
        },
    )
    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", destructive_runner)

    env = cad.run_operation(
        "transform.database.save_as",
        args={"output_path": str(protected_other.resolve())},
        write_mode="write_copy",
        dwg_path=str(original),
        out_dir=str(tmp_path / "run"),
    )

    assert runner_called is False
    assert _sha256(protected_other) == protected_sha
    assert env["executed"] is False
    assert env["status"] == "blocked"
    assert "AUTHORIZED_OUTPUT_OUTSIDE_RUN_DIRECTORY" in env["reason"]


def test_native_output_existing_inside_run_directory_is_refused_before_router_launch(
    monkeypatch, tmp_path
):
    original = tmp_path / "original.dwg"
    original.write_bytes(b"immutable source")
    output_root = tmp_path / "run"
    output_root.mkdir()
    existing_output = output_root / "existing.dwg"
    existing_output.write_bytes(b"do not replace")
    existing_sha = _sha256(existing_output)
    runner_called = False

    def destructive_runner(*args, **kwargs):
        nonlocal runner_called
        runner_called = True
        existing_output.write_bytes(b"overwritten")
        raise AssertionError("router must not replace an existing output")

    cad = cadctl.Cad()
    cad.staging_golden = tmp_path / "staging"
    monkeypatch.setattr(
        cad,
        "_registry_record",
        lambda op_id: {
            "status": "implemented",
            "write_level": {
                "default_write_mode": "write_copy",
                "allowed_write_modes": ["write_copy"],
            },
        },
    )
    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", destructive_runner)

    env = cad.run_operation(
        "transform.database.save_as",
        args={"output_path": str(existing_output.resolve())},
        write_mode="write_copy",
        dwg_path=str(original),
        out_dir=str(output_root),
    )

    assert runner_called is False
    assert _sha256(existing_output) == existing_sha
    assert env["executed"] is False
    assert env["status"] == "blocked"
    assert "AUTHORIZED_OUTPUT_ALREADY_EXISTS" in env["reason"]


def test_native_output_uses_private_path_when_requested_name_appears_after_preflight(
    monkeypatch, tmp_path
):
    original = tmp_path / "original.dwg"
    original.write_bytes(b"immutable source")
    output_root = tmp_path / "run"
    output_root.mkdir()
    requested_output = output_root / "saved.dwg"
    peer_bytes = b"concurrent peer output"
    acquire_calls = 0
    real_acquire = cadctl._acquire_operation_artifacts

    def acquire_after_peer_creation(**kwargs):
        nonlocal acquire_calls
        acquire_calls += 1
        if acquire_calls == 1:
            requested_output.write_bytes(peer_bytes)
        return real_acquire(**kwargs)

    def fake_runner(staged_dwg, run_dir, operation, *, write_mode="read", **kwargs):
        job = json.loads(Path(kwargs["job_path"]).read_text(encoding="utf-8"))
        private_output = Path(job["output_path"])
        return _router_result(
            tmp_path,
            staged_dwg,
            authorized_operation=operation,
            authorized_write_mode=write_mode,
            native_output_path=private_output,
        )

    cad = cadctl.Cad()
    cad.staging_golden = tmp_path / "staging"
    monkeypatch.setattr(
        cad,
        "_registry_record",
        lambda op_id: {
            "status": "implemented",
            "write_level": {
                "default_write_mode": "write_copy",
                "allowed_write_modes": ["write_copy"],
            },
        },
    )
    monkeypatch.setattr(cadctl, "_acquire_operation_artifacts", acquire_after_peer_creation)
    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", fake_runner)

    env = cad.run_operation(
        "transform.database.save_as",
        args={"output_path": str(requested_output.resolve())},
        write_mode="write_copy",
        dwg_path=str(original),
        out_dir=str(output_root),
    )

    assert env["status"] == "ok", env
    assert requested_output.read_bytes() == peer_bytes
    result_path = Path(env["staged_result"])
    assert result_path != requested_output
    assert result_path.read_bytes() == b"native output artifact"
    assert env["execution_receipt"]["verification"]["bound"] is True


def test_private_native_output_never_writes_a_late_hardlink_at_requested_name(
    monkeypatch, tmp_path
):
    original = tmp_path / "original.dwg"
    original.write_bytes(b"immutable source")
    protected_peer = tmp_path / "protected-peer.dwg"
    protected_bytes = b"unrelated protected drawing"
    protected_peer.write_bytes(protected_bytes)
    output_root = tmp_path / "run"
    output_root.mkdir()
    requested_output = output_root / "saved.dwg"
    acquire_calls = 0
    real_acquire = cadctl._acquire_operation_artifacts

    def acquire_after_hardlink_creation(**kwargs):
        nonlocal acquire_calls
        acquire_calls += 1
        if acquire_calls == 1:
            os.link(protected_peer, requested_output)
        return real_acquire(**kwargs)

    def fake_runner(staged_dwg, run_dir, operation, *, write_mode="read", **kwargs):
        job = json.loads(Path(kwargs["job_path"]).read_text(encoding="utf-8"))
        return _router_result(
            tmp_path,
            staged_dwg,
            authorized_operation=operation,
            authorized_write_mode=write_mode,
            native_output_path=Path(job["output_path"]),
        )

    cad = cadctl.Cad()
    cad.staging_golden = tmp_path / "staging"
    monkeypatch.setattr(
        cad,
        "_registry_record",
        lambda op_id: {
            "status": "implemented",
            "write_level": {
                "default_write_mode": "write_copy",
                "allowed_write_modes": ["write_copy"],
            },
        },
    )
    monkeypatch.setattr(cadctl, "_acquire_operation_artifacts", acquire_after_hardlink_creation)
    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", fake_runner)

    env = cad.run_operation(
        "transform.database.save_as",
        args={"output_path": str(requested_output.resolve())},
        write_mode="write_copy",
        dwg_path=str(original),
        out_dir=str(output_root),
    )

    assert env["status"] == "ok", env
    assert protected_peer.read_bytes() == protected_bytes
    assert requested_output.read_bytes() == protected_bytes
    assert os.path.samefile(protected_peer, requested_output)
    assert Path(env["staged_result"]).read_bytes() == b"native output artifact"


@pytest.mark.skipif(os.name != "nt", reason="Windows share-mode contract")
def test_native_job_arguments_are_write_locked_while_router_reads_them(
    monkeypatch, tmp_path
):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable source")
    output_root = tmp_path / "run"
    output_root.mkdir()
    requested_output = output_root / "saved.dwg"
    mutation_blocked = False

    def fake_runner(staged_dwg, run_dir, operation, *, write_mode="read", **kwargs):
        nonlocal mutation_blocked
        job_path = Path(kwargs["job_path"])
        try:
            job_path.write_text('{"output_path":"redirected.dwg"}', encoding="utf-8")
        except OSError:
            mutation_blocked = True
        job = json.loads(job_path.read_text(encoding="utf-8"))
        return _router_result(
            tmp_path,
            staged_dwg,
            authorized_operation=operation,
            authorized_write_mode=write_mode,
            native_output_path=Path(job["output_path"]),
        )

    cad = cadctl.Cad()
    cad.staging_golden = tmp_path / "staging"
    monkeypatch.setattr(
        cad,
        "_registry_record",
        lambda op_id: {
            "status": "implemented",
            "write_level": {
                "default_write_mode": "write_copy",
                "allowed_write_modes": ["write_copy"],
            },
        },
    )
    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", fake_runner)

    env = cad.run_operation(
        "transform.database.save_as",
        args={"output_path": str(requested_output.resolve())},
        write_mode="write_copy",
        dwg_path=str(source),
        out_dir=str(output_root),
    )

    assert mutation_blocked is True
    assert env["status"] == "ok", env
    assert Path(env["staged_result"]).is_file()


def test_same_timestamp_and_out_dir_still_get_distinct_execution_artifacts(
    monkeypatch, tmp_path
):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable source")
    output_root = tmp_path / "run"
    output_root.mkdir()
    requested_output = output_root / "saved.dwg"

    def fake_runner(staged_dwg, run_dir, operation, *, write_mode="read", **kwargs):
        job = json.loads(Path(kwargs["job_path"]).read_text(encoding="utf-8"))
        result = _router_result(
            Path(run_dir),
            staged_dwg,
            authorized_operation=operation,
            authorized_write_mode=write_mode,
            native_output_path=Path(job["output_path"]),
        )
        result["stdout_path"] = str(Path(run_dir) / "stdout.txt")
        result["stderr_path"] = str(Path(run_dir) / "stderr.txt")
        return result

    cad = cadctl.Cad()
    cad.staging_golden = tmp_path / "staging"
    monkeypatch.setattr(cadctl, "_ts", lambda: "fixed-stamp")
    monkeypatch.setattr(
        cad,
        "_registry_record",
        lambda op_id: {
            "status": "implemented",
            "write_level": {
                "default_write_mode": "write_copy",
                "allowed_write_modes": ["write_copy"],
            },
        },
    )
    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", fake_runner)

    envelopes = [
        cad.run_operation(
            "transform.database.save_as",
            args={"output_path": str(requested_output.resolve())},
            write_mode="write_copy",
            dwg_path=str(source),
            out_dir=str(output_root),
        )
        for _ in range(2)
    ]

    assert [env["status"] for env in envelopes] == ["ok", "ok"]
    assert requested_output.exists() is False
    assert len({env["execution_dir"] for env in envelopes}) == 2
    assert len({env["stdout"] for env in envelopes}) == 2
    assert len({env["staged_copy"] for env in envelopes}) == 2
    assert len({env["staged_result"] for env in envelopes}) == 2


def test_result_lease_blocks_replacement_through_receipt_publication(
    monkeypatch, tmp_path
):
    real_acquire = cadctl._acquire_operation_artifacts
    capture_count = 0
    blocked_swap = False

    def acquire_then_probe(**kwargs):
        nonlocal capture_count, blocked_swap
        lease = real_acquire(**kwargs)
        capture_count += 1
        if capture_count >= 2:
            assert kwargs["result"] is not None
            try:
                kwargs["result"].write_bytes(b"swap after final capture")
            except OSError:
                blocked_swap = True
        return lease

    monkeypatch.setattr(cadctl, "_acquire_operation_artifacts", acquire_then_probe)

    env = _run_with_fake(monkeypatch, tmp_path)

    assert capture_count >= 2
    assert blocked_swap is True
    assert env["status"] == "ok"
    verification = env["execution_receipt"]["verification"]
    assert verification["bound"] is True
    assert env["staged_result_sha256"] == _sha256(Path(env["staged_result"]))


@pytest.mark.parametrize(
    ("overrides", "failure_code"),
    [
        ({"include_result": False}, "RESULT_UNREPORTED"),
        ({"engine_status": None}, "REPORTED_STATUS_MISSING"),
        ({"native_status": None}, "NATIVE_STATUS_MISSING"),
        ({"engine_exit_code": 9}, "ENGINE_EXIT_NONZERO"),
        ({"process_exit_code": 7}, "PROCESS_EXIT_NONZERO"),
    ],
)
def test_incomplete_or_failed_execution_never_falls_back_to_ok(
    monkeypatch, tmp_path, overrides, failure_code
):
    env = _run_with_fake(monkeypatch, tmp_path, **overrides)

    assert env["status"] != "ok"
    verification = env["execution_receipt"]["verification"]
    assert verification["outcome_successful"] is False
    assert failure_code in verification["failure_codes"]
    if failure_code == "RESULT_UNREPORTED":
        assert verification["bound"] is False


def test_router_unavailable_is_preserved_instead_of_policy_blocked(
    monkeypatch, tmp_path
):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"synthetic immutable source")

    def unavailable_runner(staged_dwg, run_dir, operation, **kwargs):
        return {
            "command": ["fake-router"],
            "exit_code": 0,
            "stdout_path": str(tmp_path / "stdout.txt"),
            "stderr_path": str(tmp_path / "stderr.txt"),
            "envelope": {
                "schema": "ariadne.autocad_router_run.v2",
                "status": "UNAVAILABLE",
                "executed_route": "dwg_truth_autocad",
            },
            "execution": {
                "router_schema": "ariadne.autocad_router_run.v2",
                "router_status": "UNAVAILABLE",
                "executed_route": "dwg_truth_autocad",
                "process_exit_code": 0,
                "engine_exit_code": -1,
                "engine_output_exit_code": -1,
                "timed_out": False,
                "launch_error": None,
                "executed": False,
                "status": "ENGINE_UNAVAILABLE",
                "operation": operation,
                "write_mode": kwargs.get("write_mode"),
                "request_input": staged_dwg,
                "input": None,
                "result_path": None,
                "result_kind": None,
            },
            "result_json": None,
            "result": None,
            "staged_used": None,
            "timed_out": False,
            "error": None,
        }

    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", unavailable_runner)
    cad = cadctl.Cad()
    cad.staging_golden = tmp_path / "staging"

    env = cad.run_operation(
        "inspect.database.graph",
        write_mode="read",
        dwg_path=str(source),
        out_dir=str(tmp_path / "out"),
    )

    assert env["executed"] is False
    assert env["status"] == "unavailable"
    assert env["reason"] is not None


def test_pre_dispatch_refusal_still_has_a_not_executed_receipt(tmp_path):
    env = cadctl.Cad().run_operation(
        "not.in.registry",
        dwg_path=None,
        out_dir=str(tmp_path),
    )

    assert env["executed"] is False
    verification = env["execution_receipt"]["verification"]
    assert verification["bound"] is False
    assert "NOT_EXECUTED" in verification["failure_codes"]


def test_run_job_preserves_router_and_engine_execution_facts(monkeypatch, tmp_path):
    result_path = tmp_path / "result.dwg"
    result_path.write_bytes(b"router result")
    router_home = tmp_path / "router-home"
    result_json = router_home / "runs" / "native" / "result.json"
    result_json.parent.mkdir(parents=True)
    result_json.write_text(
        json.dumps({
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.database.graph",
            "status": "ok",
            "result": {"entities": []},
        }),
        encoding="utf-8",
    )
    envelope = {
        "schema": "ariadne.autocad_router_run.v2",
        "status": "PASS",
        "executed_route": "dwg_truth_autocad",
        "execution": {
            "engine_exit_code": 0,
            "engine_output": {
                "status": "ok",
                "engine_exit_code": 0,
                "executed": True,
                "operation": "inspect.database.graph",
                "write_mode": "read",
                "input_kind": "staged_copy",
                "request_input": str(tmp_path / "baseline.dwg"),
                "original_input": str(tmp_path / "baseline.dwg"),
                "input": str(result_path),
                "working_sha256_before": "a" * 64,
                "working_sha256_after": "b" * 64,
                "save_command_issued": False,
                "result_json": str(result_json),
            },
        },
    }
    completed = SimpleNamespace(
        stdout=json.dumps(envelope),
        stderr="",
        returncode=0,
    )
    monkeypatch.setattr(run_job.subprocess, "run", lambda *a, **k: completed)
    monkeypatch.setattr(run_job, "ROUTER_HOME", router_home)

    out = run_job.run_router_cad_job(
        str(tmp_path / "baseline.dwg"),
        str(tmp_path / "run"),
        "inspect.database.graph",
    )

    facts = out["execution"]
    assert facts["router_schema"] == envelope["schema"]
    assert facts["router_status"] == "PASS"
    assert facts["executed_route"] == "dwg_truth_autocad"
    assert facts["process_exit_code"] == 0
    assert facts["engine_exit_code"] == 0
    assert facts["operation"] == "inspect.database.graph"
    assert facts["write_mode"] == "read"
    assert facts["request_input"] == str(tmp_path / "baseline.dwg")
    assert facts["input"] == str(result_path)
    assert facts["native_status"] == "ok"
    assert facts["native_schema"] == "ariadne.autocad_native_job_result.v1"
    assert facts["native_engine"] == "native_objectarx"
    assert facts["native_operation"] == "inspect.database.graph"
    assert facts["native_result_source"] == "file"
    assert facts["native_result_is_object"] is True
    assert facts["native_error_code"] is None
    assert facts["native_result_path"] == str(result_json.resolve())
    assert facts["native_result_sha256"] == _sha256(result_json)
    assert out["result"] == {"entities": []}


def test_run_job_uses_native_output_path_for_save_as_result(monkeypatch, tmp_path):
    working_path = tmp_path / "router" / "input.dwg"
    working_path.parent.mkdir(parents=True)
    working_path.write_bytes(b"router working copy")
    output_path = tmp_path / "published" / "saved.dwg"
    output_path.parent.mkdir(parents=True)
    output_path.write_bytes(b"native save-as output")
    router_home = tmp_path / "router-home"
    result_json = router_home / "runs" / "native" / "result.json"
    result_json.parent.mkdir(parents=True)
    result_json.write_text(
        json.dumps({
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "transform.database.save_as",
            "status": "ok",
            "result": {"written": True, "output_path": str(output_path)},
        }),
        encoding="utf-8",
    )
    envelope = {
        "schema": "ariadne.autocad_router_run.v2",
        "status": "PASS",
        "executed_route": "dwg_truth_autocad",
        "execution": {
            "engine_exit_code": 0,
            "engine_output": {
                "status": "ok",
                "engine_exit_code": 0,
                "executed": True,
                "operation": "transform.database.save_as",
                "write_mode": "write_copy",
                "input_kind": "staged_copy",
                "request_input": str(tmp_path / "baseline.dwg"),
                "original_input": str(tmp_path / "baseline.dwg"),
                "input": str(working_path),
                "working_sha256_before": "a" * 64,
                "working_sha256_after": _sha256(working_path),
                "save_command_issued": True,
                "result_json": str(result_json),
            },
        },
    }
    completed = SimpleNamespace(
        stdout=json.dumps(envelope), stderr="", returncode=0
    )
    monkeypatch.setattr(run_job.subprocess, "run", lambda *a, **k: completed)
    monkeypatch.setattr(run_job, "ROUTER_HOME", router_home)

    out = run_job.run_router_cad_job(
        str(tmp_path / "baseline.dwg"),
        str(tmp_path / "run"),
        "transform.database.save_as",
    )

    assert out["execution"]["result_kind"] == "native_output"
    assert out["execution"]["result_path"] == str(output_path)
    assert out["staged_used"] == str(output_path)


def test_run_job_rejects_native_result_outside_router_runs(monkeypatch, tmp_path):
    router_home = tmp_path / "router-home"
    router_home.mkdir()
    result_json = tmp_path / "external-result.json"
    result_json.write_text(
        json.dumps({
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.database.graph",
            "status": "ok",
            "result": {"entities": []},
        }),
        encoding="utf-8",
    )
    envelope = {
        "schema": "ariadne.autocad_router_run.v2",
        "status": "PASS",
        "executed_route": "dwg_truth_autocad",
        "execution": {
            "engine_exit_code": 0,
            "engine_output": {
                "status": "ok",
                "engine_exit_code": 0,
                "executed": True,
                "operation": "inspect.database.graph",
                "write_mode": "read",
                "input_kind": "staged_copy",
                "request_input": str(tmp_path / "baseline.dwg"),
                "original_input": str(tmp_path / "baseline.dwg"),
                "input": str(tmp_path / "working.dwg"),
                "working_sha256_before": "a" * 64,
                "working_sha256_after": "b" * 64,
                "save_command_issued": False,
                "result_json": str(result_json),
                "result": {"entities": []},
            },
        },
    }
    completed = SimpleNamespace(
        stdout=json.dumps(envelope), stderr="", returncode=0
    )
    monkeypatch.setattr(run_job.subprocess, "run", lambda *a, **k: completed)
    monkeypatch.setattr(run_job, "ROUTER_HOME", router_home)

    out = run_job.run_router_cad_job(
        str(tmp_path / "baseline.dwg"),
        str(tmp_path / "run"),
        "inspect.database.graph",
    )

    assert out["result"] is None
    assert out["execution"]["native_status"] is None
    assert out["execution"]["native_result_path"] is None
    assert out["execution"]["native_result_sha256"] is None


def test_run_job_preserves_authoritative_structured_native_error(
    monkeypatch, tmp_path
):
    router_home = tmp_path / "router-home"
    result_json = router_home / "runs" / "native" / "result.json"
    result_json.parent.mkdir(parents=True)
    native_error = {
        "schema": "ariadne.autocad_native_job_result.v1",
        "engine": "native_objectarx",
        "operation": "inspect.database.graph",
        "status": "error",
        "error_code": "MISSING_ARG",
        "error": "required argument missing",
    }
    result_json.write_text(json.dumps(native_error), encoding="utf-8")
    envelope = {
        "schema": "ariadne.autocad_router_run.v2",
        "status": "FAIL",
        "executed_route": "dwg_truth_autocad",
        "execution": {
            "engine_exit_code": 0,
            "engine_output": {
                "status": "error",
                "engine_exit_code": 0,
                "executed": True,
                "operation": "inspect.database.graph",
                "write_mode": "read",
                "input_kind": "staged_copy",
                "request_input": str(tmp_path / "baseline.dwg"),
                "original_input": str(tmp_path / "baseline.dwg"),
                "input": str(tmp_path / "working.dwg"),
                "working_sha256_before": "a" * 64,
                "working_sha256_after": "a" * 64,
                "save_command_issued": False,
                "result_json": str(result_json),
            },
        },
    }
    completed = SimpleNamespace(
        stdout=json.dumps(envelope), stderr="", returncode=0
    )
    monkeypatch.setattr(run_job.subprocess, "run", lambda *a, **k: completed)
    monkeypatch.setattr(run_job, "ROUTER_HOME", router_home)

    out = run_job.run_router_cad_job(
        str(tmp_path / "baseline.dwg"),
        str(tmp_path / "run"),
        "inspect.database.graph",
    )

    assert out["result"] == native_error
    assert out["execution"]["native_status"] == "error"
    assert out["execution"]["native_error_code"] == "MISSING_ARG"
    assert out["execution"]["native_result_is_object"] is False
    assert out["execution"]["native_result_path"] == str(result_json.resolve())


def test_run_job_does_not_fall_back_to_inline_result_when_result_file_is_ambiguous(
    monkeypatch, tmp_path
):
    result_json = tmp_path / "result.json"
    result_json.write_text(
        '{"status":"ok","status":"error"}', encoding="utf-8"
    )
    envelope = {
        "schema": "ariadne.autocad_router_run.v2",
        "status": "PASS",
        "executed_route": "dwg_truth_autocad",
        "execution": {
            "engine_exit_code": 0,
            "engine_output": {
                "status": "ok",
                "engine_exit_code": 0,
                "executed": True,
                "result_json": str(result_json),
                "result": {"status": "ok"},
            },
        },
    }
    completed = SimpleNamespace(
        stdout=json.dumps(envelope), stderr="", returncode=0
    )
    monkeypatch.setattr(run_job.subprocess, "run", lambda *a, **k: completed)

    out = run_job.run_router_cad_job(
        str(tmp_path / "baseline.dwg"),
        str(tmp_path / "run"),
        "inspect.database.graph",
    )

    assert out["result"] is None
    assert out["execution"]["native_status"] is None


@pytest.mark.parametrize(
    "payload",
    [
        '{"status":"ok","status":"error"}',
        '{"status":"ok","value":NaN}',
        '{"status":"ok","value":Infinity}',
    ],
)
def test_router_stdout_parser_rejects_ambiguous_json(payload):
    assert run_job._parse_first_json_object(payload) is None


@pytest.mark.parametrize(
    "execution",
    [
        "not-an-object",
        {"engine_output": "not-an-object"},
    ],
)
def test_run_job_treats_malformed_nested_execution_as_missing_facts(
    monkeypatch, tmp_path, execution
):
    envelope = {
        "schema": "ariadne.autocad_router_run.v2",
        "status": "PASS",
        "executed_route": "dwg_truth_autocad",
        "execution": execution,
    }
    completed = SimpleNamespace(
        stdout=json.dumps(envelope), stderr="", returncode=0
    )
    monkeypatch.setattr(run_job.subprocess, "run", lambda *a, **k: completed)

    out = run_job.run_router_cad_job(
        str(tmp_path / "baseline.dwg"),
        str(tmp_path / "run"),
        "inspect.database.graph",
    )

    assert out["result"] is None
    assert out["result_json"] is None
    assert out["execution"]["executed"] is None
    assert out["execution"]["native_status"] is None
