"""Guard the MCP SDK installation matrix against silent false passes."""
from __future__ import annotations

from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]


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
