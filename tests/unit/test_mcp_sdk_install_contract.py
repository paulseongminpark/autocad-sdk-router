"""Guard the MCP SDK installation matrix against silent false passes."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


_ROOT = Path(__file__).resolve().parents[2]


def _powershell_executable() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def test_shared_sdk_is_pinned_to_the_verified_v1_release():
    requirements = (_ROOT / "requirements.txt").read_text(encoding="utf-8")
    mcp_lines = [line.strip() for line in requirements.splitlines()
                 if line.strip().startswith("mcp")]
    assert mcp_lines == ["mcp==1.27.1"]
    assert "457" not in requirements


def test_matrix_checks_native_exit_codes_and_the_actual_v2_import():
    script = (_ROOT / "tools" / "test_cadagent_mcp_sdk_matrix.ps1").read_text(
        encoding="utf-8")
    assert "function Invoke-CheckedNative" in script
    assert "$exitCode = $LASTEXITCODE" in script
    assert "$exitCode -ne 0" in script
    assert 'throw "$Label failed with exit code $exitCode."' in script
    # v1 pytest, isolated pip install, v2 import verification, and v2 pytest.
    assert script.count("Invoke-CheckedNative") >= 5
    assert "& $PythonExe" not in script
    assert "importlib.metadata.version('mcp')" in script
    assert "mcp.__file__" in script
    assert "CADAGENT_MCP_V2_TARGET" in script
    assert "expected mcp==1.27.1" in script
    assert "module_path.is_relative_to(target)" in script
    assert "$v1HadPythonPath" in script
    assert "$v1HadV2Target" in script


def test_v1_lane_cannot_pass_when_inherited_environment_points_at_v2():
    """The v1 lane must prove its import before its pytest process starts."""
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for the SDK matrix regression test")

    v2_target = Path(os.environ.get(
        "CADAGENT_MCP_V2_TARGET",
        Path(os.environ.get("TEMP", ".")) / "cadagent-mcp-sdk-v2",
    )).resolve()
    if not (v2_target / "mcp-2.0.0.dist-info").is_dir():
        pytest.skip("isolated mcp==2.0.0 target is not installed")

    script = _ROOT / "tools" / "test_cadagent_mcp_sdk_matrix.ps1"
    command = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$env:PYTHONPATH = $env:TEST_V2_TARGET",
        "$env:CADAGENT_MCP_V2_TARGET = 'sentinel-before-matrix'",
        "& $env:TEST_MATRIX_SCRIPT -PythonExe $env:TEST_PYTHON -V2Target $env:TEST_V2_TARGET",
        "$matrixExit = $LASTEXITCODE",
        "Write-Output ('AFTER_PYTHONPATH=' + $env:PYTHONPATH)",
        "Write-Output ('AFTER_CADAGENT_MCP_V2_TARGET=' + $env:CADAGENT_MCP_V2_TARGET)",
        "exit $matrixExit",
    ])
    env = os.environ.copy()
    env.update({
        "TEST_MATRIX_SCRIPT": str(script),
        "TEST_PYTHON": sys.executable,
        "TEST_V2_TARGET": str(v2_target),
    })
    completed = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    v1_lines = [line for line in output.splitlines()
                if line.startswith("MCP_V1_IMPORT_OK ")]
    assert len(v1_lines) == 1, output
    assert "version=1.27.1" in v1_lines[0], output
    assert str(v2_target).casefold() not in v1_lines[0].casefold(), output
    assert f"AFTER_PYTHONPATH={v2_target}" in output, output
    assert "AFTER_CADAGENT_MCP_V2_TARGET=sentinel-before-matrix" in output, output


def test_mcp_contract_doc_describes_the_official_sdk_wire_surface():
    contract = (_ROOT / "docs" / "MCP_TOOL_CONTRACT.md").read_text(
        encoding="utf-8"
    )
    assert "official Python MCP SDK" in contract
    assert "19" in contract
    assert "resources/list" in contract
    assert "resources/templates/list" in contract
    assert "CallToolResult" in contract
    assert "isError=true" in contract
    assert "structuredContent=null" in contract
    assert "hidden legacy aliases" in contract
    assert "omitted" in contract and "explicit JSON null" in contract
    assert "structured error" in contract
    assert "transport == \"mock\"" not in contract
    assert "tools=12" not in contract


def test_install_docs_pin_the_shared_mcp_sdk_v1_dependency():
    install = (_ROOT / "INSTALL.md").read_text(encoding="utf-8")
    assert "mcp==1.27.1" in install
    assert "jsonschema + MCP SDK v1" in install
    assert "only dependency is `jsonschema`" not in install


def test_installer_checks_every_native_dependency_and_router_call():
    installer = (_ROOT / "install.ps1").read_text(encoding="utf-8")
    assert "function Invoke-CheckedNative" in installer
    assert "$exitCode = $LASTEXITCODE" in installer
    assert "$exitCode -ne 0" in installer
    assert 'throw "$Label failed with exit code $exitCode."' in installer
    # version, core pip, optional full pip, router smoke, executable resolution
    assert installer.count("Invoke-CheckedNative") >= 6
    assert "& $PythonExe" not in installer
    assert "& (Join-Path $Root 'tools\\autocad-router.ps1')" not in installer
    assert "catch { $pyAbs = '' }" not in installer
