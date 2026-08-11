from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _workflow_text() -> str:
    assert WORKFLOW.is_file(), "GitHub CI workflow is missing"
    return WORKFLOW.read_text(encoding="utf-8")


def test_ci_runs_on_pull_requests_and_main_pushes() -> None:
    text = _workflow_text()
    assert "pull_request:" in text
    assert "push:" in text
    assert "branches: [main]" in text
    assert "permissions:\n  contents: read" in text


def test_ci_has_all_four_release_contract_jobs() -> None:
    text = _workflow_text()
    for job in (
        "python-tests:",
        "mcp-sdk-matrix:",
        "powershell-syntax:",
        "native-integrity:",
    ):
        assert job in text
    assert "python -m pytest tests -q" in text
    assert "test_cadagent_mcp_sdk_matrix.ps1" in text
    assert "System.Management.Automation.Language.Parser" in text
    assert "test_native_deployment_consumers.py" in text


def test_ci_jobs_are_bounded_and_use_read_only_repository_permissions() -> None:
    text = _workflow_text()
    assert text.count("runs-on: windows-latest") == 4
    assert text.count("timeout-minutes:") == 4
    assert "cancel-in-progress: true" in text
