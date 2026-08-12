from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / "tools" / "autocad-router.ps1"
CORE_FACT_KEYS = {
    "status",
    "engine_exit_code",
    "executed",
    "operation",
    "write_mode",
    "input_kind",
    "request_input",
    "original_input",
    "input",
    "working_sha256_before",
    "working_sha256_after",
    "save_command_issued",
}


def _function_source(name: str) -> str:
    source = ROUTER.read_text(encoding="utf-8-sig")
    start = source.index(f"function {name} {{")
    next_function = source.find("\nfunction ", start + 1)
    return source[start:] if next_function < 0 else source[start:next_function]


def _powershell() -> str:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        raise AssertionError("PowerShell is required for the router contract test")
    return exe


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_cad_job_result(
    result_path: Path,
    *,
    expected_operation: str,
    expected_schema: str = "ariadne.autocad_native_job_result.v1",
    expected_engine: str = "native_objectarx",
    inline_max_mb: int = 24,
) -> dict:
    script = (
        _function_source("Read-CadJobResultSafe")
        + "\n$result = Read-CadJobResultSafe "
        + "-ResultPath $env:ARIADNE_TEST_RESULT_PATH "
        + "-ExpectedOperation $env:ARIADNE_TEST_EXPECTED_OPERATION "
        + "-ExpectedSchema $env:ARIADNE_TEST_EXPECTED_SCHEMA "
        + "-ExpectedEngine $env:ARIADNE_TEST_EXPECTED_ENGINE "
        + f"-InlineMaxMB {inline_max_mb}\n"
        + "$result | ConvertTo-Json -Depth 100 -Compress"
    )
    env = os.environ.copy()
    env["ARIADNE_TEST_RESULT_PATH"] = str(result_path)
    env["ARIADNE_TEST_EXPECTED_OPERATION"] = expected_operation
    env["ARIADNE_TEST_EXPECTED_SCHEMA"] = expected_schema
    env["ARIADNE_TEST_EXPECTED_ENGINE"] = expected_engine
    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_cad_job_result_accepts_only_the_exact_success_contract(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    expected = {
        "schema": "ariadne.autocad_native_job_result.v1",
        "engine": "native_objectarx",
        "operation": "inspect.entity",
        "status": "ok",
        "result": {"handle": "1A"},
    }
    _write_json(result_path, expected)

    actual = _read_cad_job_result(
        result_path, expected_operation="inspect.entity"
    )

    assert actual["Ok"] is True
    assert actual["Inline"] == expected
    assert actual["SizeBytes"] == result_path.stat().st_size


@pytest.mark.parametrize(
    "payload",
    [
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "status": "ok",
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "status": "ok",
            "result": None,
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "status": "ok",
            "result": [],
        },
    ],
    ids=["missing-result", "null-result", "array-result"],
)
def test_native_success_requires_an_object_result(
    tmp_path: Path, payload: dict
) -> None:
    result_path = tmp_path / "result.json"
    _write_json(result_path, payload)

    actual = _read_cad_job_result(
        result_path, expected_operation="inspect.entity"
    )

    assert actual["Ok"] is False


def test_cad_job_result_rejects_a_missing_file(tmp_path: Path) -> None:
    actual = _read_cad_job_result(
        tmp_path / "missing.json", expected_operation="inspect.entity"
    )

    assert actual == {"Ok": False, "Inline": None, "SizeBytes": 0}


@pytest.mark.parametrize("error_code", [None, ""])
def test_cad_job_result_allows_only_empty_error_codes(
    tmp_path: Path, error_code: str | None
) -> None:
    result_path = tmp_path / "result.json"
    _write_json(
        result_path,
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "status": "ok",
            "error_code": error_code,
            "result": {},
        },
    )

    actual = _read_cad_job_result(
        result_path, expected_operation="inspect.entity"
    )

    assert actual["Ok"] is True


def test_cad_job_result_rejects_the_wrong_schema(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    _write_json(
        result_path,
        {
            "schema": "ariadne.autocad_native_job_result.v0",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "status": "ok",
        },
    )

    actual = _read_cad_job_result(
        result_path, expected_operation="inspect.entity"
    )

    assert actual["Ok"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "managed_dotnet",
            "operation": "inspect.entity",
            "status": "ok",
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.other",
            "status": "ok",
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "status": "ok",
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "status": "blocked",
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "status": "unknown",
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "status": "error",
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "status": "ok",
            "error_code": "NATIVE_FAILURE",
        },
        {
            "schema": ["ariadne.autocad_native_job_result.v1"],
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "status": "ok",
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": ["native_objectarx"],
            "operation": "inspect.entity",
            "status": "ok",
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": ["inspect.entity"],
            "status": "ok",
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "status": ["ok"],
        },
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "status": "ok",
            "error_code": [],
        },
    ],
    ids=[
        "wrong-engine",
        "wrong-operation",
        "missing-operation",
        "missing-status",
        "blocked-status",
        "unknown-status",
        "error-status",
        "nonempty-error-code",
        "schema-must-be-a-string",
        "engine-must-be-a-string",
        "operation-must-be-a-string",
        "status-must-be-a-string",
        "error-code-must-be-null-or-a-string",
    ],
)
def test_cad_job_result_rejects_any_non_success_contract_field(
    tmp_path: Path, payload: dict
) -> None:
    result_path = tmp_path / "result.json"
    _write_json(result_path, payload)

    actual = _read_cad_job_result(
        result_path, expected_operation="inspect.entity"
    )

    assert actual["Ok"] is False


@pytest.mark.parametrize(
    "raw_json",
    [
        "{",
        "[]",
        "null",
        '"ok"',
        "123",
        (
            '{"schema":"wrong","schema":"ariadne.autocad_native_job_result.v1",'
            '"engine":"native_objectarx","operation":"inspect.entity",'
            '"status":"ok"}'
        ),
        (
            '{"schema":"ariadne.autocad_native_job_result.v1",'
            '"engine":"native_objectarx","operation":"inspect.entity",'
            '"status":"ok","result":{"value":1,"value":2}}'
        ),
        (
            '{"schema":"ariadne.autocad_native_job_result.v1",'
            '"engine":"native_objectarx","operation":"inspect.entity",'
            '"status":"ok","result":{"value":NaN}}'
        ),
        (
            '{"schema":"ariadne.autocad_native_job_result.v1",'
            '"engine":"native_objectarx","operation":"inspect.entity",'
            '"status":"ok","result":{"value":Infinity}}'
        ),
        (
            '{"schema":"ariadne.autocad_native_job_result.v1",'
            '"engine":"native_objectarx","operation":"inspect.entity",'
            '"status":"ok","result":{"value":-Infinity}}'
        ),
    ],
    ids=[
        "malformed",
        "array",
        "null",
        "string",
        "number",
        "duplicate-top-level-key",
        "duplicate-nested-key",
        "nan",
        "positive-infinity",
        "negative-infinity",
    ],
)
def test_cad_job_result_rejects_non_strict_json(
    tmp_path: Path, raw_json: str
) -> None:
    result_path = tmp_path / "result.json"
    result_path.write_text(raw_json, encoding="utf-8")

    actual = _read_cad_job_result(
        result_path, expected_operation="inspect.entity"
    )

    assert actual["Ok"] is False


def test_cad_job_result_never_trusts_only_a_large_file_tail(tmp_path: Path) -> None:
    result_path = tmp_path / "large-result.json"
    _write_json(
        result_path,
        {
            "schema": "ariadne.autocad_native_job_result.v1",
            "engine": "native_objectarx",
            "operation": "inspect.entity",
            "padding": "x" * 100,
            "status": "ok",
        },
    )

    actual = _read_cad_job_result(
        result_path,
        expected_operation="inspect.entity",
        inline_max_mb=0,
    )

    assert actual == {
        "Ok": False,
        "Inline": None,
        "SizeBytes": result_path.stat().st_size,
    }


def _make_no_cad_router_home(
    tmp_path: Path, *, engine_result: dict | None = None
) -> tuple[Path, Path, Path]:
    router_home = tmp_path / "router-home"
    (router_home / "tools").mkdir(parents=True)
    (router_home / "config").mkdir(parents=True)
    managed_dir = (
        router_home
        / "src"
        / "Ariadne.DwgGeometryExtractor"
        / "bin"
        / "Release"
        / "net10.0-windows"
    )
    managed_dir.mkdir(parents=True)
    (managed_dir / "Ariadne.DwgGeometryExtractor.dll").write_bytes(b"not-loaded")

    fake_engine = router_home / "fake-accoreconsole.cmd"
    fake_engine_lines = [
        "@echo off",
        '> "%~dp0engine-launched.txt" echo launched',
    ]
    if engine_result is not None:
        fake_engine_lines.append(
            f'> "%ARIADNE_CAD_JOB_OUT%" echo {json.dumps(engine_result)}'
        )
    fake_engine_lines.append("exit /b 0")
    fake_engine.write_text(
        "\r\n".join(fake_engine_lines) + "\r\n",
        encoding="ascii",
    )
    probe = router_home / "tools" / "probe_routes.py"
    probe.write_text(
        "import argparse, json\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('--out', required=True)\n"
        "a = p.parse_args()\n"
        "payload = {'routes': {'dwg_truth_autocad': "
        "{'available': True, 'required': []}}}\n"
        "open(a.out, 'w', encoding='utf-8').write(json.dumps(payload))\n",
        encoding="utf-8",
    )
    capabilities = {
        "intent_aliases": {"dwg": "dwg_truth_autocad"},
        "routes": [
            {
                "id": "dwg_truth_autocad",
                "priority": 1,
                "engine": "contract_fake",
                "engine_path": str(fake_engine),
                "entrypoint": "contract",
                "tools": [],
                "can_do": "contract",
                "intents": ["dwg"],
                "fallback_to": [],
            }
        ],
    }
    config = router_home / "config" / "autocad_router_capabilities.json"
    _write_json(config, capabilities)
    _write_json(
        router_home / "config" / "operations.v2.json",
        {
            "operations": [
                {
                    "id": "managed.contract",
                    "handler": {
                        "router_lane": "MANAGED_CAD_JOB",
                        "execution_host_class": "coreconsole",
                    },
                }
            ]
        },
    )
    return router_home, config, fake_engine


def _run_managed(
    tmp_path: Path,
    *,
    write_mode: str,
    include_input: bool = True,
    engine_result: dict | None = None,
) -> tuple[dict, Path, Path | None]:
    router_home, config, fake_engine = _make_no_cad_router_home(
        tmp_path, engine_result=engine_result
    )
    input_path = router_home / "request.dwg" if include_input else None
    if input_path:
        input_path.write_bytes(b"contract-dwg")
    env = os.environ.copy()
    env["ARIADNE_ACAD_ENGINE_PATH"] = str(fake_engine)
    env.pop("ARIADNE_NATIVE_ACAD_BIN_DIR", None)
    command = [
        _powershell(),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ROUTER),
        "-Action",
        "run",
        "-Intent",
        "dwg",
        "-Operation",
        "managed.contract",
        "-WriteMode",
        write_mode,
        "-RouterHome",
        str(router_home),
        "-ConfigPath",
        str(config),
        "-PythonExe",
        sys.executable,
    ]
    if input_path:
        command.extend(["-InputPath", str(input_path)])
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout), router_home, input_path


@pytest.mark.parametrize("write_mode", ["write_copy", "live_edit"])
def test_managed_unsafe_write_mode_fails_closed_before_autocad_launch(
    tmp_path: Path, write_mode: str
) -> None:
    envelope, router_home, input_path = _run_managed(
        tmp_path, write_mode=write_mode
    )

    execution = envelope["execution"]
    output = execution["engine_output"]
    assert CORE_FACT_KEYS <= output.keys()
    assert output == {
        **output,
        "status": "MANAGED_WRITE_MODE_UNSUPPORTED",
        "engine_exit_code": -17,
        "executed": False,
        "operation": "managed.contract",
        "write_mode": write_mode,
        "input_kind": "staged_copy",
        "request_input": str(input_path),
        "original_input": str(input_path),
        "input": None,
        "working_sha256_before": None,
        "working_sha256_after": None,
        "save_command_issued": False,
    }
    assert execution["engine_exit_code"] == output["engine_exit_code"]
    assert output["limitation_code"] == "MANAGED_WRITE_MODE_NOT_PROVEN_SAFE"
    assert not (router_home / "engine-launched.txt").exists()


def test_managed_read_reports_the_actual_working_copy_and_hashes(tmp_path: Path) -> None:
    envelope, router_home, input_path = _run_managed(tmp_path, write_mode="read")

    execution = envelope["execution"]
    output = execution["engine_output"]
    expected_sha256 = hashlib.sha256(b"contract-dwg").hexdigest()
    assert CORE_FACT_KEYS <= output.keys()
    assert output["status"] == "cad_job_failed"
    assert output["engine_exit_code"] == -3
    assert output["executed"] is True
    assert output["operation"] == "managed.contract"
    assert output["write_mode"] == "read"
    assert output["input_kind"] == "staged_copy"
    assert output["request_input"] == str(input_path)
    assert output["original_input"] == str(input_path)
    assert output["input"] != str(input_path)
    assert Path(output["input"]).is_file()
    assert output["working_sha256_before"] == expected_sha256
    assert output["working_sha256_after"] == expected_sha256
    assert output["save_command_issued"] is False
    assert execution["engine_exit_code"] == output["engine_exit_code"]
    assert (router_home / "engine-launched.txt").is_file()


def test_router_envelope_never_passes_an_invalid_job_result(tmp_path: Path) -> None:
    invalid_result = {
        "schema": "ariadne.autocad_native_job_result.v1",
        "engine": "native_objectarx",
        "operation": "managed.contract",
        "status": "unknown",
    }

    envelope, _, _ = _run_managed(
        tmp_path,
        write_mode="read",
        engine_result=invalid_result,
    )

    assert envelope["status"] == "ROUTE_NONZERO"
    assert envelope["execution"]["engine_exit_code"] == -3
    assert envelope["execution"]["engine_output"]["status"] == "cad_job_failed"
    assert envelope["execution"]["engine_output"]["result"] is None


def test_managed_success_result_yields_router_pass(tmp_path: Path) -> None:
    managed_result = {
        "schema": "ariadne.autocad_sdk_job_result.v1",
        "engine": "managed_objectarx_active_document",
        "operation": "managed.contract",
        "status": "ok",
        "result": {"entities": 1},
    }

    envelope, _, _ = _run_managed(
        tmp_path,
        write_mode="read",
        engine_result=managed_result,
    )

    assert envelope["status"] == "PASS"
    assert envelope["execution"]["engine_exit_code"] == 0
    assert envelope["execution"]["engine_output"]["status"] == "ok"
    assert envelope["execution"]["engine_output"]["result"] == managed_result


def test_native_and_managed_job_results_share_the_provenance_shape() -> None:
    body = _function_source("Invoke-CadJobRoute")
    native_start = body.index("if (Test-NativeP1CadJobOperation")
    managed_start = body.index("$dll = Resolve-NativeExtractorDll", native_start)
    native_block = body[native_start:managed_start]
    managed_block = body[managed_start:]

    for block in (native_block, managed_block):
        assert "engine_output = New-CadJobEngineOutput" in block
        assert "Read-CadJobResultSafe" in block
        assert "-ResultPath $resultOut" in block
        assert "-ExpectedOperation $jobOperation" in block
        assert "-OperationName $jobOperation" in block
        assert "-EffectiveWriteMode $effectiveWriteMode" in block
        assert "-InputKind $inputKind" in block
        assert "-RequestInput $InputPath" in block
        assert "-WorkingInput $inputDwg" in block
        assert "-WorkingSha256Before $workingSha256Before" in block
        assert "-WorkingSha256After $workingSha256After" in block
        assert "-SaveCommandIssued" in block

    assert "-ExpectedSchema 'ariadne.autocad_native_job_result.v1'" in native_block
    assert "-ExpectedEngine 'native_objectarx'" in native_block
    assert "-ExpectedSchema 'ariadne.autocad_sdk_job_result.v1'" in managed_block
    assert "-ExpectedEngine 'managed_objectarx_active_document'" in managed_block

    assert "if ($effectiveWriteMode -eq 'write_original')" in managed_block
    assert "$scrLines += 'QSAVE'" in managed_block


def test_cad_job_early_error_is_structured_and_missing_facts_are_null(
    tmp_path: Path,
) -> None:
    envelope, router_home, input_path = _run_managed(
        tmp_path, write_mode="read", include_input=False
    )

    execution = envelope["execution"]
    output = execution["engine_output"]
    assert input_path is None
    assert CORE_FACT_KEYS <= output.keys()
    assert output == {
        **output,
        "status": "INPUT_REQUIRED",
        "engine_exit_code": -1,
        "executed": False,
        "operation": "managed.contract",
        "write_mode": "read",
        "input_kind": None,
        "request_input": None,
        "original_input": None,
        "input": None,
        "working_sha256_before": None,
        "working_sha256_after": None,
        "save_command_issued": False,
    }
    assert execution["engine_exit_code"] == output["engine_exit_code"]
    assert not (router_home / "engine-launched.txt").exists()


def test_full_autocad_job_is_explicitly_unbound_and_does_not_broaden_qsave() -> None:
    body = _function_source("Invoke-FullAutoCadCadJob")

    assert "engine_output = [ordered]" not in body
    assert 'engine_output = "' not in body
    assert "engine_output = '" not in body
    assert body.count("engine_output = New-FullAutoCadCadJobEngineOutput") == 8
    assert "-InputKind 'active_document'" in _function_source(
        "New-FullAutoCadCadJobEngineOutput"
    )
    assert "-WorkingInput $null" in _function_source(
        "New-FullAutoCadCadJobEngineOutput"
    )
    assert "FULL_AUTOCAD_DOCUMENT_IDENTITY_UNBOUND" in _function_source(
        "New-FullAutoCadCadJobEngineOutput"
    )
    assert "@('write_copy', 'write_original', 'live_edit') -contains " in body
    assert body.count("$scrLines += '_QSAVE'") == 1
